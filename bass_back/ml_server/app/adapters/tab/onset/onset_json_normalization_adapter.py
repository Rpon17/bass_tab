from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.onset.onset_json_noramization_port import (
    OnsetNormalizeParams,
    OnsetNormalizePort,
)

"""
    
"""


@dataclass(frozen=True)
class OnsetNormalizeAdapter(OnsetNormalizePort):
    output_filename: str = "onset_note_normalization.json"

    def normalize(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: OnsetNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        if not notes:
            return []

        merge_gap_seconds: float = params.merge_gap_seconds
        conf_threshold: float = params.conf_threshold

        filtered: list[BasicPitchNoteEventDTO] = self._filter_events(
            notes=notes,
            conf_threshold=conf_threshold,
        )

        sorted_notes: list[BasicPitchNoteEventDTO] = self._sort_events(notes=filtered)

        merged: list[BasicPitchNoteEventDTO] = self._merge_adjacent_same_pitch_events(
            notes=sorted_notes,
            merge_gap_seconds=merge_gap_seconds,
        )

        closed: list[BasicPitchNoteEventDTO] = self._close_octave(
            notes=merged,
            params=params,
        )

        out = closed
        
        return out

    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_json_dir: Path,
        params: OnsetNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        if not input_json_path.exists():
            raise FileNotFoundError(f"input json not found: {input_json_path}")

        output_json_path: Path = output_json_dir / self.output_filename

        if output_json_path.exists() and not overwrite:
            return output_json_path

        
        notes: list[BasicPitchNoteEventDTO] = self._load_notes_json(path=input_json_path)

        normalized: list[BasicPitchNoteEventDTO] = self.normalize(
            notes=notes,
            params=params,
        )

        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_notes_json(path=output_json_path, notes=normalized)

        return output_json_path


    # start_time < end_time 혹은 conf가 기준치(0.35) 이하
    def _filter_events(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        conf_threshold: float,
    ) -> list[BasicPitchNoteEventDTO]:
        filtered: list[BasicPitchNoteEventDTO] = []
        for n in notes:
            start_time: float = float(n.start_time)
            end_time: float = float(n.end_time)
            if end_time <= start_time:
                continue

            conf: float | None = n.confidence
            if conf is not None and float(conf) <= float(conf_threshold):
                continue

            filtered.append(
                BasicPitchNoteEventDTO(
                    start_time=start_time,
                    end_time=end_time,
                    pitch_midi=int(n.pitch_midi),
                    confidence=None if conf is None else float(conf),
                )
            )
        return filtered

    # 정렬한번 더 함
    def _sort_events(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
    ) -> list[BasicPitchNoteEventDTO]:
        return sorted(
            notes,
            key=lambda n: (float(n.start_time), float(n.end_time), int(n.pitch_midi)),
        )

    # merge함 간격 (0.2)
    def _merge_adjacent_same_pitch_events(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        merge_gap_seconds: float,
    ) -> list[BasicPitchNoteEventDTO]:
        if not notes:
            return []

        merged: list[BasicPitchNoteEventDTO] = []
        for n in notes:
            if not merged:
                merged.append(n)
                continue

            prev: BasicPitchNoteEventDTO = merged[-1]
            gap: float = float(n.start_time) - float(prev.end_time)

            if int(n.pitch_midi) == int(prev.pitch_midi) and gap <= float(merge_gap_seconds):
                merged[-1] = BasicPitchNoteEventDTO(
                    start_time=float(prev.start_time),
                    end_time=float(max(float(prev.end_time), float(n.end_time))),
                    pitch_midi=int(prev.pitch_midi),
                    confidence=self._merge_confidence(
                        prev_conf=prev.confidence,
                        n_conf=n.confidence,
                    ),
                )
            else:
                merged.append(n)

        return merged

    # confidence 무조건 높은거로 가져감
    def _merge_confidence(
        self,
        *,
        prev_conf: float | None,
        n_conf: float | None,
    ) -> float | None:
        if prev_conf is None and n_conf is None:
            return None
        if prev_conf is None:
            return float(n_conf) 
        if n_conf is None:
            return float(prev_conf)
        return float(max(float(prev_conf), float(n_conf)))

    # 가까운데 너무 큰 옥타브차이 -> 물리적으로 불가능
    def _close_octave(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: OnsetNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        """  
            1. 만약에 너무 짧은 시간안데 너무 큰 이동이있다면 물리적으로 불가능 -> 옥타브 튐
            2. 하지만 0번 프렛은 예외이므로 0번 프렛인 후보들은 제외하고 결정.
        """

        if not notes:
            return []

        fast_jump_sec = params.fast_jump_sec
        fast_jump_semitones = params.fast_jump_semitones
        snap_only_octave = params.snap_only_octave

        default_num = params.default

        skip_pitch: set[int] = set(range(default_num, 71, 5))

        midi_min = params.midi_min
        midi_max = params.midi_max

        def _clamp_pitch(p: int) -> int:
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

            is_skip: bool = (cur_pitch in skip_pitch) or (prev_pitch in skip_pitch)

            if should_consider and (not is_skip):
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

    def _load_notes_json(self, *, path: Path) -> list[BasicPitchNoteEventDTO]:
        raw: Any
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, list):
            raise ValueError(f"note events json must be a list: {path}")

        out: list[BasicPitchNoteEventDTO] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            start_time_obj: object = item.get("start_time", item.get("start_time_s"))
            end_time_obj: object = item.get("end_time", item.get("end_time_s"))
            if start_time_obj is None or end_time_obj is None:
                continue

            try:
                start_time: float = float(start_time_obj)
                end_time: float = float(end_time_obj)
            except (TypeError, ValueError):
                continue

            pitch_obj: object = item.get("pitch_midi", item.get("pitch"))
            if pitch_obj is None:
                continue

            try:
                pitch_midi: int = int(pitch_obj)
            except (TypeError, ValueError):
                continue

            conf_obj: object = item.get("confidence", item.get("conf", None))
            confidence: float | None
            try:
                confidence = None if conf_obj is None else float(conf_obj)
            except (TypeError, ValueError):
                confidence = None

            out.append(
                BasicPitchNoteEventDTO(
                    start_time=start_time,
                    end_time=end_time,
                    pitch_midi=pitch_midi,
                    confidence=confidence,
                )
            )

        return out

    def _save_notes_json(
        self,
        *,
        path: Path,
        notes: list[BasicPitchNoteEventDTO],
    ) -> None:
        payload: list[dict[str, object]] = [
            {
                "start_time": float(n.start_time),
                "end_time": float(n.end_time),
                "pitch_midi": int(n.pitch_midi),
                "confidence": None if n.confidence is None else float(n.confidence),
            }
            for n in notes
        ]

        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)