from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.application.ports.tab_normalization_port import (
    TabNormalizationPort,
    TabNormalizationResultPort,
    TabNormalizationUseCasePort,
)
from app.adapters.tab.tab_dto import NoteEvent


@dataclass(frozen=True)
class TabNormalizationAdapter(TabNormalizationUseCasePort):
    """
        1. onset과 offset이 너무 가까우면 제외함
        2. merge 만약 두 피치가 알고보니 이어지는 연결이었다면? offset 연장
        (같은피치인데 검출오류)
        3. min-gap 너무 가까운 재타격 제거 -> 이거 사람이 쳤을 가능성이 말이안된다싶은정도
        (이것도 검출오류)
        4. 같은 시간에 두가지 음 -> 하나 제거
        5. 옥타브 보정
            5.1 -> -24,-12,0,+12,+24로 과연 오류가 있었는지 한번 보정을 갈김
            5.2 -> 앞뒤로 10개씩 보면서 12피치 이상 차이나는게 있는지 한번 봄
    주의:
      - req에 bpm이 없으므로 시간 임계값은 "초 단위"로 기본값을 둔다.
      - 나중에 bpm을 입력받도록 req를 확장하면, min_dur/merge_gap/min_gap을 bpm 기반으로 스케일링 가능.
    """

    # 최종 result
    output_filename: str = "note_events.normalized.json"

    # 종이반의반의반장차이
    epsilon_sec: float = 1e-3

    # 최소 offset-onset -> 더이상 큰상관x
    min_duration_sec: float = 0.001

    # merge -> 이 이하면 붙이기 (연장음감지)
    merge_gap_sec: float = 0.01

    # min-gap -> 이 이하면 제거 (재타격감지)
    min_gap_sec: float = 0.01

    # 앞뒤 10개(총 최대 21개)로 로컬 median 계산
    local_window_radius: int = 10  
    
    # 로컬 median 기준 ±12
    band_half_width: int = 12       
    
    # 첫음은 무조건 이거보다 높다 
    min_valid_pitch_midi = 40
    
    # 밴드 밖에 패널티
    band_penalty: int = 6           

    # 이 이상 튀면 옥타브 스냅을 적극 적용
    octave_snap_threshold: int = 10  

    async def normalize_and_save(
        self,
        *,
        req: TabNormalizationPort,
    ) -> TabNormalizationResultPort:
        note_events_json_path: Path = req.note_events_json_path
        output_dir: Path = req.output_dir

        if not note_events_json_path.exists():
            raise FileNotFoundError(
                f"note_events_json_path not found: {note_events_json_path}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        events: list[NoteEvent] = self._load_note_events(
            note_events_json_path=note_events_json_path
        )

        # 이벤트라는것을 정의한다..
        events = [e for e in events if (e.offset_sec > e.onset_sec + self.epsilon_sec)]

        # onset기준으로 정렬
        events = sorted(events, key=lambda e: (e.onset_sec, e.offset_sec, e.pitch_midi))

        # 너무짧은거 삭제함
        events = self._drop_too_short(events=events)

        # merge 병합
        events = self._merge_same_pitch(events=events)

        # 너무짧은거 한번 더 삭제
        events = self._drop_too_short(events=events)

        # 옥타브보정
        events = self._stabilize_octaves(events=events)

        # 재타격 제거
        events = self._drop_too_close_retriggers(events=events)

        # 모노포닉 제거
        events = self._drop_overlaps_monophonic(events=events)

        # 마지막으로 정렬
        events = sorted(events, key=lambda e: (e.onset_sec, e.offset_sec, e.pitch_midi))

        # 저장
        out_path: Path = output_dir / self.output_filename
        payload: list[dict[str, Any]] = [
            {
                "onset_sec": round(e.onset_sec, 6),
                "offset_sec": round(e.offset_sec, 6),
                "pitch_midi": int(e.pitch_midi),
                "confidence": (
                    round(float(e.confidence), 6) if e.confidence is not None else None
                ),
            }
            for e in events
        ]
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return TabNormalizationResultPort(normalized_note_events_json_path=out_path)

    # 노트이벤트 로드
    def _load_note_events(
        self,
        *,
        note_events_json_path: Path,
    ) -> list[NoteEvent]:
        raw_text: str = note_events_json_path.read_text(encoding="utf-8")
        payload: Any = json.loads(raw_text)

        rows: list[dict[str, Any]] = []

        # list와 dict만 허용함
        if isinstance(payload, list):
            rows = [r for r in payload if isinstance(r, dict)]
        elif isinstance(payload, dict):
            maybe_rows: Any = payload.get("note_events") or payload.get("notes") or payload.get("events")
            if isinstance(maybe_rows, list):
                rows = [r for r in maybe_rows if isinstance(r, dict)]
        # else: rows=[]

        out: list[NoteEvent] = []
        for r in rows:
            onset_raw: Any = (
                r.get("onset_sec")
                or r.get("start_time")
                or r.get("start_time_s")
                or r.get("onset")
            )
            offset_raw: Any = (
                r.get("offset_sec")
                or r.get("end_time")
                or r.get("end_time_s")
                or r.get("offset")
            )
            pitch_raw: Any = r.get("pitch_midi") or r.get("pitch")

            if onset_raw is None or offset_raw is None or pitch_raw is None:
                continue

            try:
                onset_sec: float = float(onset_raw)
                offset_sec: float = float(offset_raw)
                pitch_midi: int = int(round(float(pitch_raw)))
            except Exception:
                continue

            conf_raw: Any = r.get("confidence") or r.get("amplitude") or r.get("velocity")
            confidence: float | None
            try:
                confidence = float(conf_raw) if conf_raw not in (None, "") else None
            except Exception:
                confidence = None

            # velocity가 1.0 초과 범위(예: 127)면 정규화
            if confidence is not None and confidence > 1.0:
                confidence = min(confidence / 127.0, 1.0)

            out.append(
                NoteEvent(
                    onset_sec=onset_sec,
                    offset_sec=offset_sec,
                    pitch_midi=pitch_midi,
                    confidence=confidence,
                )
            )

        return out

    # 너무 짧은거는 자른다
    def _drop_too_short(
        self,
        *,
        events: list[NoteEvent],
    ) -> list[NoteEvent]:
        out: list[NoteEvent] = []
        # 만약 offset과 onset의 차가 기준치에 도달 못한다면 무시함
        for e in events:
            dur_sec: float = e.offset_sec - e.onset_sec
            if dur_sec + self.epsilon_sec < self.min_duration_sec:
                continue
            out.append(e)
        return out

    # merge계산(이어붙이기)
    def _merge_same_pitch(
        self,
        *,
        events: list[NoteEvent],
    ) -> list[NoteEvent]:
        if not events:
            return []

        merged: list[NoteEvent] = []
        cur: NoteEvent = events[0]

        """
            1번부터 시작해서 돌기시작함 다음피치가 현재피치와 같다면
            다음의 onset시간과 현재의 offset시간을 뺀다
            근데 너무 가까워서 기준 미달이라면 이건 병합한다
        """
        for nxt in events[1:]:
            if nxt.pitch_midi == cur.pitch_midi:
                gap_sec: float = nxt.onset_sec - cur.offset_sec

                if gap_sec <= self.merge_gap_sec + self.epsilon_sec:
                    new_onset: float = cur.onset_sec
                    new_offset: float = max(cur.offset_sec, nxt.offset_sec)

                    # cinfidence도 설정해줘야함 둘중 높은거로 감
                    cur_conf: float | None = cur.confidence
                    nxt_conf: float | None = nxt.confidence

                    if cur_conf is None and nxt_conf is None:
                        new_conf: float | None = None
                    elif cur_conf is None:
                        new_conf = nxt_conf
                    elif nxt_conf is None:
                        new_conf = cur_conf
                    else:
                        new_conf = max(cur_conf, nxt_conf)

                    cur = NoteEvent(
                        onset_sec=new_onset,
                        offset_sec=new_offset,
                        pitch_midi=cur.pitch_midi,
                        confidence=new_conf,
                    )
                    continue

            # 병합 안 하면 cur 확정
            merged.append(cur)
            cur = nxt

        merged.append(cur)
        return sorted(merged, key=lambda x: (x.onset_sec, x.offset_sec, x.pitch_midi))


    def _stabilize_octaves(
        self,
        *,
        events: list[NoteEvent],
    ) -> list[NoteEvent]:
        """
            A) 연속성 기반 스냅:
               후보 {p0-24, p0-12, p0, p0+12, p0+24} 중에서
               ref(직전 확정 pitch)와의 |diff|가 최소인 후보를 고른다.

            B) 로컬 분포 기반 band:
               i번째 이벤트 기준으로 [i-R, i+R] 윈도우에서 median을 구하고,
               band=[median-band_half_width, median+band_half_width]를 만든다.
               band 밖 후보는 band_penalty 페널티를 부여해서 구간별 주 대역을 유지한다.

            + "40 기준"을 원하므로, min_valid_pitch_midi 미만 후보는 큰 페널티로 거의 배제한다.

            적용은 보수적으로:
              - abs(p0-ref)가 octave_snap_threshold 이상일 때는 스냅을 적극 적용
              - 그보다 작으면(이미 안정) 그대로 두되, 40 미만이면 보정한다
              
        """
        """   
            +-24,12하면서 비교함 
        """
        if not events:
            return []

        out: list[NoteEvent] = []

        # 첫음을 잡는데 저 40기준으로 함 안되면 
        first_pitch: int = int(events[0].pitch_midi)
        if first_pitch < int(self.min_valid_pitch_midi):
            ref_pitch+=12
        else:
            ref_pitch = first_pitch

        n_events: int = len(events)

        for i, e in enumerate(events):
            p0: int = int(e.pitch_midi)

            # 앞뒤로 10개씩 평균내서 얼마나 가까운지
            left: int = max(0, i - int(self.local_window_radius))
            right: int = min(n_events, i + int(self.local_window_radius) + 1)  # slice는 end exclusive

            # 각각의 pitches만 삭 꺼내옴
            window_pitches: list[int] = [int(x.pitch_midi) for x in events[left:right]]
            ws: list[int] = sorted(window_pitches)
            wn: int = len(ws)
            mid: int = wn // 2
            if wn % 2 == 1:
                local_median = int(ws[mid])
            else:
                local_median = int(round((ws[mid - 1] + ws[mid]) / 2.0))

            band_min: int = int(local_median - int(self.band_half_width))
            band_max: int = int(local_median + int(self.band_half_width))

            # ----- A) 연속성 기반 후보 선택 -----
            candidates: list[int] = [p0 - 24, p0 - 12, p0, p0 + 12, p0 + 24]
            candidates = [p for p in candidates if p >= 0]

            best_p: int = p0
            best_cost: float = 1e18

            for p in candidates:
                # 연속성 비용(가장 중요)
                cost: float = float(abs(int(p) - int(ref_pitch)))

                # 로컬 band 밖이면 페널티
                if p < band_min or p > band_max:
                    cost += float(self.band_penalty)

                # 40 기준 하한(사실상 배제)
                if p < int(self.min_valid_pitch_midi):
                    cost += 1000.0

                # 동률이면 더 낮은 pitch 선호(불필요한 상향 스냅 방지)
                if cost < best_cost or (cost == best_cost and p < best_p):
                    best_cost = cost
                    best_p = int(p)

            # 보수적으로: 크게 튀면 스냅, 아니면 유지(단 40 미만은 보정)
            if abs(p0 - ref_pitch) >= int(self.octave_snap_threshold):
                chosen_pitch: int = best_p
            else:
                if p0 < int(self.min_valid_pitch_midi):
                    chosen_pitch = best_p
                else:
                    chosen_pitch = p0

            out.append(
                NoteEvent(
                    onset_sec=float(e.onset_sec),
                    offset_sec=float(e.offset_sec),
                    pitch_midi=int(chosen_pitch),
                    confidence=e.confidence,
                )
            )
            ref_pitch = int(chosen_pitch)

        return out

    # 너무 빠르게 같은 피치가 재등장하면 버림
    def _drop_too_close_retriggers(
        self,
        *,
        events: list[NoteEvent],
    ) -> list[NoteEvent]:
        """
        """
        if not events:
            return []

        # 최종적으로 남길 친구들
        out: list[NoteEvent] = []
        # 그 피치의 마지막으로 채택된 친구
        last_by_pitch: dict[int, NoteEvent] = {}

        for e in events:
            # 이전이 디폴트는 없는건데 피치가 같다면 이전거 가져옴
            prev: NoteEvent | None = last_by_pitch.get(e.pitch_midi)
            # 만약 pitch가 처음 나오면 그냥 채택함
            if prev is None:
                out.append(e)
                last_by_pitch[e.pitch_midi] = e
                continue

            # 지금 onset시간과 이전 onset시간이 너무 가깝다
            gap_onset_sec: float = e.onset_sec - prev.onset_sec
            if gap_onset_sec < self.min_gap_sec - self.epsilon_sec:
                # 재타격 -> 이건 말이안된다 바로제거
                continue

            out.append(e)
            last_by_pitch[e.pitch_midi] = e

        # 무조건정렬
        return sorted(out, key=lambda x: (x.onset_sec, x.offset_sec, x.pitch_midi))

    # 한순간에 하나의 음만 남김
    def _drop_overlaps_monophonic(
        self,
        *,
        events: list[NoteEvent],
    ) -> list[NoteEvent]:
        """
            이전의 offset보다 현재의 onset이 빠르면 제거
        """
        if not events:
            return []

        kept: list[NoteEvent] = []
        prev: NoteEvent | None = None

        for e in events:
            if prev is None:
                kept.append(e)
                prev = e
                continue

            if e.onset_sec < prev.offset_sec - self.epsilon_sec:
                # 제거함
                continue

            kept.append(e)
            prev = e
        return kept
