from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import (
    BasicPitchFramePitchDTO,
    BasicPitchNoteEventDTO,
)
from app.application.ports.tab.frame.frame_note_normalization_port import (
    FramePitchNormalizeParams,
    FramePitchNormalizePort,
)

"""
    input_json -> 이건 옥타브 보정을 먼저 한 원시 json파일
    최종 : sort -> conf_cut -> frames_to_onset -> merge -> 마지막 보정
    최종 : sort -> frames_to_onset -> merge -> 마지막 보정 -> conf_cut 
"""


@dataclass(frozen=True)
class FramePitchNormalizeAdapter(FramePitchNormalizePort):
    output_filename: str = "frame_note_normalize.json"

    def normalize(
        self,
        *,
        notes: list[BasicPitchFramePitchDTO],
        params: FramePitchNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        if not notes:
            return []

        frames_any: list[dict[str, Any]] = [
            {
                "t": float(n.t),
                "pitch_midi": int(n.pitch_midi),
                "confidence": None if n.confidence is None else float(n.confidence),
            }
            for n in notes
        ]

        frames_sorted: list[dict[str, Any]] = sorted(frames_any, key=lambda r: float(r["t"]))

        runs: list[BasicPitchNoteEventDTO] = self._frames_to_onset(
            frames=frames_sorted,
            params=params,
        )

        merged: list[BasicPitchNoteEventDTO] = self._merge_gap(
            notes=sorted(runs, key=lambda n: (float(n.start_time), float(n.end_time))),
            merge_gap_seconds=float(params.merge_gap_seconds),
        )

        closed_octave: list[BasicPitchNoteEventDTO] = self._close_octave(
            notes=merged,
            params=params,
        )

        notes_confidence_cutted: list[BasicPitchNoteEventDTO] = self._confidence_cut_notes(
            notes=closed_octave,
            params=params,
        )

        out: list[BasicPitchNoteEventDTO] = self._min_duration_cut(
            notes=notes_confidence_cutted,
            params=params,
        )

        return out

    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_dir: Path,
        params: FramePitchNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        if not input_json_path.exists():
            raise FileNotFoundError(f"input json not found: {input_json_path}")

        out_dir: Path = output_dir
        out_path: Path = out_dir / self.output_filename
        if out_path.exists() and not overwrite:
            return out_path

        frames_any: list[dict[str, Any]] = self._load_list_json(path=input_json_path)

        frames_sorted: list[dict[str, Any]] = sorted(frames_any, key=lambda r: float(r["t"]))

        # (옵션 A) 프레임 단계에서 confidence cut
        # frames_sorted = self._confidence_cut_frames(frames=frames_sorted, params=params)

        runs: list[BasicPitchNoteEventDTO] = self._frames_to_onset(
            frames=frames_sorted,
            params=params,
        )

        merged: list[BasicPitchNoteEventDTO] = self._merge_gap(
            notes=sorted(runs, key=lambda n: (float(n.start_time), float(n.end_time))),
            merge_gap_seconds=float(params.merge_gap_seconds),
        )

        closed_octave: list[BasicPitchNoteEventDTO] = self._close_octave(
            notes=merged,
            params=params,
        )

        # (옵션 B) 노트 단계에서 confidence cut
        notes_confidence_cutted: list[BasicPitchNoteEventDTO] = self._confidence_cut_notes(
            notes=closed_octave,
            params=params,
        )

        out: list[BasicPitchNoteEventDTO] = self._min_duration_cut(
            notes=notes_confidence_cutted,
            params=params,
        )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_notes_json(path=out_path, notes=out)
        return out_path

    # list로 로드
    def _load_list_json(self, *, path: Path) -> list[dict[str, Any]]:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"frame json must be list: {path}")

        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            if "t" not in item or ("pitch_midi" not in item and "pitch" not in item):
                continue

            t: float = float(item["t"])
            p: int = int(item.get("pitch_midi", item.get("pitch")))
            c_obj: object = item.get("confidence", item.get("conf", None))
            conf: float | None = None if c_obj is None else float(c_obj)

            out.append({"t": t, "pitch_midi": p, "confidence": conf})
        return out

    # confidence로 컷 (frames 버전)
    @staticmethod
    def _confidence_cut_frames(
        *,
        frames: list[dict[str, Any]],
        params: FramePitchNormalizeParams,
    ) -> list[dict[str, Any]]:
        if not frames:
            return []

        conf_threshold: float = float(params.conf_threshold)

        out: list[dict[str, Any]] = []
        for n in frames:
            conf_obj: object = n.get("confidence")
            if conf_obj is None:
                continue
            conf: float = float(conf_obj)
            if conf < conf_threshold:
                continue

            out.append(
                {
                    "t": float(n.get("t", 0.0)),
                    "pitch_midi": int(n.get("pitch_midi", 0)),
                    "confidence": conf,
                }
            )
        return out

    # confidence로 컷 (notes 버전)
    @staticmethod
    def _confidence_cut_notes(
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: FramePitchNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        if not notes:
            return []

        conf_threshold: float = float(params.conf_threshold)

        out: list[BasicPitchNoteEventDTO] = []
        for n in notes:
            if n.confidence is None:
                continue
            conf: float = float(n.confidence)
            if conf < conf_threshold:
                continue
            out.append(n)
        return out

    # merge
    def _merge_gap(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        merge_gap_seconds: float,
    ) -> list[BasicPitchNoteEventDTO]:
        if not notes:
            return []

        out: list[BasicPitchNoteEventDTO] = []
        for n in notes:
            if not out:
                out.append(n)
                continue

            prev: BasicPitchNoteEventDTO = out[-1]
            gap: float = float(n.start_time) - float(prev.end_time)

            if int(n.pitch_midi) == int(prev.pitch_midi) and 0.0 <= gap <= float(merge_gap_seconds):
                out[-1] = BasicPitchNoteEventDTO(
                    start_time=float(prev.start_time),
                    end_time=float(max(float(prev.end_time), float(n.end_time))),
                    pitch_midi=int(prev.pitch_midi),
                    confidence=self._merge_conf(prev.confidence, n.confidence),
                )
            else:
                out.append(n)

        return out

    # 둘중 높은 conf 돌려줌
    def _merge_conf(self, a: float | None, b: float | None) -> float | None:
        if a is None and b is None:
            return None
        if a is None:
            return float(b)
        if b is None:
            return float(a)
        return float(max(float(a), float(b)))

    # frames -> onset
    def _frames_to_onset(
        self,
        *,
        frames: list[dict[str, Any]],
        params: FramePitchNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        if not frames:
            return []

        mt: float = float(params.maximum_divide_time)  # 이보다 크면 run 끊음
        dt: float = float(params.default_plus_time)  # 끝에 조금 더해 흔적만 남김

        out: list[BasicPitchNoteEventDTO] = []

        cur_p: int = int(frames[0]["pitch_midi"])
        start_t: float = float(frames[0]["t"])
        last_t: float = float(frames[0]["t"])

        confs: list[float] = []
        c0: object = frames[0].get("confidence", None)
        if c0 is not None:
            try:
                confs.append(float(c0))
            except Exception:
                pass

        for r in frames[1:]:
            t: float = float(r["t"])
            p: int = int(r["pitch_midi"])
            c_obj: object = r.get("confidence", None)

            t_gap: float = t - last_t
            gap_break: bool = t_gap > mt
            pitch_break: bool = p != cur_p

            if gap_break or pitch_break:
                out.append(
                    BasicPitchNoteEventDTO(
                        start_time=float(start_t),
                        end_time=float(last_t) + float(dt),
                        pitch_midi=int(cur_p),
                        confidence=max(confs),
                    )
                )

                cur_p = p
                start_t = t
                last_t = t
                confs = []
                if c_obj is not None:
                    try:
                        confs.append(float(c_obj))
                    except Exception:
                        pass
                continue

            last_t = t
            if c_obj is not None:
                try:
                    confs.append(float(c_obj))
                except Exception:
                    pass

        out.append(
            BasicPitchNoteEventDTO(
                start_time=float(start_t),
                end_time=float(last_t) + float(dt),
                pitch_midi=int(cur_p),
                confidence=self._median(confs),
            )
        )
        return out

    # 적어도 하나는 merge 해야 살려주는 옵션
    def _min_duration_cut(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: FramePitchNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        min_seconds: float = float(params.min_note_seconds)
        return [n for n in notes if (float(n.end_time) - float(n.start_time)) >= min_seconds]

    # 중앙값
    def _median(self, values: list[float]) -> float | None:
        if not values:
            return None
        vs: list[float] = sorted(float(v) for v in values)
        mid: int = len(vs) // 2
        if len(vs) % 2 == 1:
            return float(vs[mid])
        return float((vs[mid - 1] + vs[mid]) / 2.0)

    def _save_notes_json(self, *, path: Path, notes: list[BasicPitchNoteEventDTO]) -> None:
        payload: list[dict[str, object]] = [
            {
                "start_time": float(n.start_time),
                "end_time": float(n.end_time),
                "pitch_midi": int(n.pitch_midi),
                "confidence": None if n.confidence is None else float(n.confidence),
            }
            for n in notes
        ]
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _close_octave(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: FramePitchNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        """  
            1. 만약에 너무 짧은 시간안데 너무 큰 이동이있다면 물리적으로 불가능 -> 옥타브 튐
            2. 하지만 0번 프렛은 예외이므로 0번 프렛인 후보들은 제외하고 결정.
        """

        if not notes:
            return []

        fast_jump_sec: float = float(params.fast_jump_sec) if float(params.fast_jump_sec) > 0.0 else 0.20
        fast_jump_semitones: int = int(params.fast_jump_semitones) if int(params.fast_jump_semitones) > 0 else 10
        snap_only_octave: bool = bool(params.snap_only_octave)

        default_num: int = int(params.default)
        skip_pitch: set[int] = set(range(default_num, 71, 5))

        midi_min_obj: Any = params.midi_min
        midi_max_obj: Any = params.midi_max
        midi_min: int | None = None if midi_min_obj is None else int(midi_min_obj)
        midi_max: int | None = None if midi_max_obj is None else int(midi_max_obj)

        def _clamp_pitch(p: int) -> int:
            # 단순 clamp가 아니라, 옥타브 단위로 범위 안으로 밀어넣는 방식
            if midi_min is not None:
                while p < midi_min:
                    p += 12
            if midi_max is not None:
                while p > midi_max:
                    p -= 12
            return int(p)

        # note와 pitch가 있으면 교체함
        def _replace_pitch(note: BasicPitchNoteEventDTO, new_pitch: int) -> BasicPitchNoteEventDTO:
            return replace(note, pitch_midi=int(new_pitch))

        # 현재 pitch를 가까운 후보 pitch로 바꿈
        def _closest_octave_pitch(cur: int, target: int) -> int:
            k0: int = int(round((target - cur) / 12.0))
            best: int = cur
            best_d: int = abs(cur - target)

            for k in (k0 - 2, k0 - 1, k0, k0 + 1, k0 + 2):
                cand: int = cur + 12 * k
                d: int = abs(cand - target)
                if d < best_d:
                    best = cand
                    best_d = d

            return best

        out: list[BasicPitchNoteEventDTO] = list(notes)

        prev_pitch: int = int(out[0].pitch_midi)
        prev_end_time: float = float(out[0].end_time)

        for i in range(1, len(out)):
            cur_note: BasicPitchNoteEventDTO = out[i]
            cur_pitch: int = int(cur_note.pitch_midi)
            cur_start_time: float = float(cur_note.start_time)

            dt: float = cur_start_time - prev_end_time
            dp: int = cur_pitch - prev_pitch

            should_consider: bool = (dt <= fast_jump_sec) and (abs(dp) >= fast_jump_semitones)

            if should_consider:
                if snap_only_octave and abs(dp) == 12:
                    fixed: int = prev_pitch
                else:
                    fixed = _closest_octave_pitch(cur=cur_pitch, target=prev_pitch)

                fixed = _clamp_pitch(int(fixed))

                if fixed != cur_pitch:
                    out[i] = _replace_pitch(cur_note, fixed)
                    cur_pitch = fixed

            prev_pitch = cur_pitch
            prev_end_time = float(cur_note.end_time)

        return out