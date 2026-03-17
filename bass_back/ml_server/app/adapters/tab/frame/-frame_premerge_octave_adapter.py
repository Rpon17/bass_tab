from __future__ import annotations

import json
from dataclasses import dataclass
from math import inf
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import (
    BasicPitchFramePitchDTO,
    BasicPitchNoteEventDTO,
)
from app.application.ports.tab.frame.frame_premerge_octave_port import (
    FramePitchOctaveNormalizeParams,
    FramePitchOctaveNormalizePort,
)


@dataclass(frozen=True)
class FramePitchOctaveNormalizeAdapter(FramePitchOctaveNormalizePort):
    """
    파이프라인 (이벤트 기반)
      frames -> premerge(note_events) -> close_octave(note_events) -> viterbi(note_events)
    """

    output_filename: str = "note_events_premerged_octave.json"

    # -------------------- public --------------------

    def normalize(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: FramePitchOctaveNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        if not frames:
            return []

        merged_events: list[BasicPitchNoteEventDTO] = self._premerge(frames=frames, params=params)
        if not merged_events:
            return []

        cleaned_events: list[BasicPitchNoteEventDTO] = self._fix_instant_octave_jumps_events(
            events=merged_events,
            params=params,
        )
        if not cleaned_events:
            return []

        return self._viterbi_events(events=cleaned_events, params=params)

    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_dir: Path,
        params: FramePitchOctaveNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        if not input_json_path.exists():
            raise FileNotFoundError(f"input not found: {input_json_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path: Path = output_dir / self.output_filename

        if output_path.exists() and not overwrite:
            return output_path

        with input_json_path.open("r", encoding="utf-8") as f:
            raw_obj: object = json.load(f)

        frames_raw: list[BasicPitchFramePitchDTO] = self._parse_frames_json(raw_obj)

        out_events: list[BasicPitchNoteEventDTO] = self.normalize(
            frames=frames_raw,
            params=params,
        )

        payload: list[dict[str, Any]] = [
            {
                "start_time": float(ev.start_time),
                "end_time": float(ev.end_time),
                "pitch_midi": int(ev.pitch_midi),
                "confidence": None if ev.confidence is None else float(ev.confidence),
            }
            for ev in out_events
        ]

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return output_path


    def _merge_conf(self, a: float | None, b: float | None) -> float | None:
        if a is None and b is None:
            return None
        if a is None:
            return b
        if b is None:
            return a
        return a if a >= b else b

    
    def _premerge(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: FramePitchOctaveNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        """
        frame(t, pitch, conf) -> note_event(start_time, end_time, pitch, conf)

        - 시간 정렬
        - 같은 pitch가 연속으로 나오고, 프레임 간 간격이 premerge_sec 이하면 하나의 note로 merge
        - note confidence는 (None 제외) 최대값 사용 (_merge_conf)
        - merge된 구간 길이가 unmerged_t 보다 짧으면 'merge하지 않고' 프레임 단위 이벤트로 쪼개서 반환
        """
        premerge_sec: float = float(params.premerge_sec)
        unmerged_t: float = float(params.unmerged_t)

        if premerge_sec <= 0.0:
            raise ValueError("premerge_sec must be > 0")

        if not frames:
            return []

        frames_sorted: list[BasicPitchFramePitchDTO] = sorted(frames, key=lambda f: float(f.t))

        out: list[BasicPitchNoteEventDTO] = []

        seg_pitch: int = int(frames_sorted[0].pitch_midi)
        seg_start: float = float(frames_sorted[0].t)
        seg_last_t: float = float(frames_sorted[0].t)
        seg_conf: float | None = frames_sorted[0].confidence
        seg_frames: list[BasicPitchFramePitchDTO] = [frames_sorted[0]]

        def flush(*, next_t: float | None) -> None:
            nonlocal seg_pitch, seg_start, seg_last_t, seg_conf, seg_frames, out

            default_end: float = float(seg_last_t + premerge_sec)
            seg_end: float = default_end if next_t is None else float(min(default_end, next_t))
            if seg_end <= seg_start:
                seg_end = float(seg_start + premerge_sec)

            duration: float = float(seg_end - seg_start)

            if duration < unmerged_t:
                # merge하지 않고 프레임 단위로 쪼갬 (end_time은 다음 프레임 t, 마지막은 t+premerge_sec)
                n: int = int(len(seg_frames))
                for i in range(n):
                    f: BasicPitchFramePitchDTO = seg_frames[i]
                    st: float = float(f.t)

                    if i + 1 < n:
                        et: float = float(seg_frames[i + 1].t)
                        if et <= st:
                            et = float(st + premerge_sec)
                    else:
                        et = float(st + premerge_sec)

                    out.append(
                        BasicPitchNoteEventDTO(
                            start_time=st,
                            end_time=et,
                            pitch_midi=int(f.pitch_midi),
                            confidence=f.confidence,
                        )
                    )
            else:
                out.append(
                    BasicPitchNoteEventDTO(
                        start_time=seg_start,
                        end_time=seg_end,
                        pitch_midi=int(seg_pitch),
                        confidence=seg_conf,
                    )
                )

        for idx in range(1, len(frames_sorted)):
            f: BasicPitchFramePitchDTO = frames_sorted[idx]
            t: float = float(f.t)
            pitch: int = int(f.pitch_midi)
            conf: float | None = f.confidence

            dt: float = float(t - seg_last_t)

            if pitch == seg_pitch and dt <= premerge_sec:
                seg_last_t = t
                seg_conf = self._merge_conf(seg_conf, conf)  # ✅ max conf
                seg_frames.append(f)
                continue

            flush(next_t=t)

            seg_pitch = pitch
            seg_start = t
            seg_last_t = t
            seg_conf = conf
            seg_frames = [f]

        flush(next_t=None)
        return out

    # -------------------- close_octave (events -> events) --------------------

    def _fix_instant_octave_jumps_events(
        self,
        *,
        events: list[BasicPitchNoteEventDTO],
        params: FramePitchOctaveNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        """
        premerge 이후,
        dt <= params.octave_close 이내에 pitch 차이가 정확히 ±12면 "옥타브 튐"으로 정의하고 관측값을 교정한다.

        교정 정책:
        - 바로 이전 pitch로 강제 스냅(= 튄 값을 오류 관측으로 간주)
        """
        if not events:
            return []

        octave_close: float = float(getattr(params, "octave_close", 0.03))
        if octave_close <= 0.0:
            octave_close = 0.03

        out: list[BasicPitchNoteEventDTO] = [events[0]]
        prev: BasicPitchNoteEventDTO = events[0]

        for i in range(1, len(events)):
            cur: BasicPitchNoteEventDTO = events[i]
            dt: float = abs(float(cur.start_time) - float(prev.start_time))
            dp: int = int(cur.pitch_midi) - int(prev.pitch_midi)

            if dt <= octave_close and abs(dp) == 12:
                out.append(
                    BasicPitchNoteEventDTO(
                        start_time=float(cur.start_time),
                        end_time=float(cur.end_time),
                        pitch_midi=int(prev.pitch_midi),
                        confidence=cur.confidence,
                    )
                )
                prev = out[-1]
                continue

            out.append(cur)
            prev = cur

        return out

    # -------------------- viterbi (events -> events) --------------------

    def _viterbi_events(
        self,
        *,
        events: list[BasicPitchNoteEventDTO],
        params: FramePitchOctaveNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        """
        관측값(obs_pitch)은 '이벤트의 pitch_midi'로 두고,
        상태는 obs_pitch + offset (alias_semitones) 후보들 중에서
        emission(= alias 벌점 * conf 가중) + transition(연속성) 최소 경로를 선택.

        적용 시: start/end/confidence는 유지하고 pitch_midi만 보정한다.
        """
        if not events:
            return []

        offsets: list[int] = [int(k) for k in params.alias_semitones]
        if 0 not in offsets:
            offsets = [0] + offsets

        S: int = int(len(offsets))
        T: int = int(len(events))

        prev_idx: list[list[int]] = [[-1] * S for _ in range(T)]
        prev_cost: list[float] = [inf] * S
        cur_cost: list[float] = [inf] * S

        # t=0
        conf0: float | None = events[0].confidence
        for s in range(S):
            prev_cost[s] = self._emission_cost_offset(
                offset=int(offsets[s]),
                obs_conf=conf0,
                params=params,
            )
            prev_idx[0][s] = -1

        # DP
        for t in range(1, T):
            obs_pitch: int = int(events[t].pitch_midi)
            obs_conf: float | None = events[t].confidence

            cur_state_pitches: list[int] = [int(obs_pitch + k) for k in offsets]
            emit_costs: list[float] = [
                self._emission_cost_offset(
                    offset=int(k),
                    obs_conf=obs_conf,
                    params=params,
                )
                for k in offsets
            ]

            prev_obs_pitch: int = int(events[t - 1].pitch_midi)

            for s in range(S):
                best_cost: float = inf
                best_pi: int = -1
                cur_pitch: int = int(cur_state_pitches[s])

                for p in range(S):
                    prev_pitch: int = int(prev_obs_pitch + offsets[p])

                    trans: float = self._transition_cost(
                        prev_pitch=int(prev_pitch),
                        cur_pitch=int(cur_pitch),
                        params=params,
                    )
                    c: float = float(prev_cost[p]) + float(trans)

                    if c < best_cost:
                        best_cost = float(c)
                        best_pi = int(p)

                cur_cost[s] = float(best_cost) + float(emit_costs[s])
                prev_idx[t][s] = int(best_pi)

            prev_cost, cur_cost = cur_cost, [inf] * S

        # backtrace
        last_state: int = int(min(range(S), key=lambda i: float(prev_cost[i])))
        path_state_idx: list[int] = [0] * T
        path_state_idx[T - 1] = int(last_state)

        for t in range(T - 1, 0, -1):
            path_state_idx[t - 1] = int(prev_idx[t][path_state_idx[t]])

        # apply
        midi_min: int = int(params.midi_min)
        midi_max: int = int(params.midi_max)

        out: list[BasicPitchNoteEventDTO] = []
        for t in range(T):
            obs_pitch: int = int(events[t].pitch_midi)
            best_offset: int = int(offsets[path_state_idx[t]])

            st_pitch: int = int(obs_pitch + best_offset)
            if st_pitch < midi_min:
                st_pitch = int(midi_min)
            if st_pitch > midi_max:
                st_pitch = int(midi_max)

            ev: BasicPitchNoteEventDTO = events[t]
            out.append(
                BasicPitchNoteEventDTO(
                    start_time=float(ev.start_time),
                    end_time=float(ev.end_time),
                    pitch_midi=int(st_pitch),
                    confidence=ev.confidence,
                )
            )

        return out

    # -------------------- helpers --------------------

    @staticmethod
    def _parse_frames_json(obj: object) -> list[BasicPitchFramePitchDTO]:
        if not isinstance(obj, list):
            raise ValueError("frames json must be a list of objects")

        out: list[BasicPitchFramePitchDTO] = []
        for i, row_obj in enumerate(obj):
            if not isinstance(row_obj, dict):
                raise ValueError(f"frames[{i}] must be an object")

            t_obj: object = row_obj.get("t")
            pitch_obj: object = row_obj.get("pitch_midi", row_obj.get("pitch"))
            conf_obj: object = row_obj.get("confidence", row_obj.get("conf"))

            if t_obj is None or pitch_obj is None:
                raise ValueError(f"frames[{i}] missing required keys: t, pitch_midi")

            t: float = float(t_obj)
            pitch_midi: int = int(pitch_obj)
            confidence: float | None = None if conf_obj is None else float(conf_obj)

            out.append(
                BasicPitchFramePitchDTO(
                    t=float(t),
                    pitch_midi=int(pitch_midi),
                    confidence=confidence,
                )
            )

        return out

    def _emission_cost_offset(
        self,
        *,
        offset: int,
        obs_conf: float | None,
        params: FramePitchOctaveNormalizeParams,
    ) -> float:
        conf_floor: float = float(params.conf_floor)
        conf_power: float = float(params.conf_power)
        conf_default: float = float(params.conf_default)
        conf_cost: float = float(params.conf_cost)

        c: float = conf_floor if obs_conf is None else float(obs_conf)

        if c < conf_floor:
            c = conf_floor
        if c > 1.0:
            c = 1.0

        conf_w: float = float(c**conf_power)

        octs: int = abs(int(offset)) // 12
        alias_pen: float = float(octs) * float(params.alias_cost_per_octave)

        return float(alias_pen) * float(conf_default + conf_cost * conf_w)

    def _transition_cost(
        self,
        *,
        prev_pitch: int,
        cur_pitch: int,
        params: FramePitchOctaveNormalizeParams,
    ) -> float:
        dp: int = abs(int(cur_pitch) - int(prev_pitch))

        # 너무 큰 dp를 그대로 벌점주면 과고정될 수 있어 캡핑
        step_cost: float = float(params.lambda_step) * float(min(int(dp), 12))

        is_oct_like: bool = (int(dp) % 12 == 0)
        oct_cost: float = float(params.lambda_oct) if is_oct_like else 0.0

        return float(step_cost + oct_cost)