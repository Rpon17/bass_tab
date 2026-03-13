from __future__ import annotations

import json
from dataclasses import dataclass
from math import floor
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.merge.original.onset_frame_plus_port import OnsetFrameFuseParams
from app.application.ports.tab.merge.root.root_note_port import RootTabBuildPort


@dataclass(frozen=True)
class RootTabBuildAdapter(RootTabBuildPort):

    output_filename: str = "root.json"
    """  
        락은 4/4박이다!
    """

    def build(
        self,
        *,
        bpm: float,
        original_notes: list[BasicPitchNoteEventDTO],
        params: OnsetFrameFuseParams,
    ) -> list[BasicPitchNoteEventDTO]:
        notes: list[BasicPitchNoteEventDTO] = sorted(
            [n for n in original_notes],
            key=lambda n: (float(n.start_time), float(n.end_time), int(n.pitch_midi)),
        )

        if not notes:
            return []

        bpm_f: float = float(bpm)
        if bpm_f <= 0.0:
            raise ValueError("bpm 너무낮음")

        beats_per_bar: int = int(params.beats_per_bar)
        if beats_per_bar <= 0:
            raise ValueError("비트가 너무작음")

        # 1박 -> 0.3초
        one_bak_sec: float = 60.0 / bpm_f
        # 1마디 -> 4박
        one_madi_sec: float = one_bak_sec * float(beats_per_bar)

        t_start: float = float(notes[0].start_time)
        t_end: float = float(notes[-1].end_time)

        # 처음으로 시작해야할 바의 인덱스
        start_madi_idx: int = int(floor(t_start / one_madi_sec))
        # 마지막으로 치면 될 바의 인덱스
        last_madi_idx: int = int(floor((t_end - 1e-9) / one_madi_sec))

        out: list[BasicPitchNoteEventDTO] = []

        i: int = 0
        note_lengh: int = len(notes)

        #
        for madi_idx in range(start_madi_idx, last_madi_idx + 1):

            # 마디가 시작되는 시간
            madi_start: float = float(madi_idx) * one_madi_sec
            # 마디가 끝나는 시간
            madi_end: float = madi_start + one_madi_sec

            # madi의 start시간이 notes[i]를 넘겼다면 notes[i]는 이미 넘어갔으니 i를 더해 다음노트의
            # 루트를 검사한다 그리고 시간이 지날수록 [i]를 더한다
            # 즉 i -> 이미 검사가 끝나고 건너뛴 위치
            while i < note_lengh and float(notes[i].end_time) <= madi_start:
                i += 1

            root_pitch: int | None = None
            root_conf: float | None = None

            # j에 i를 저장함 그리고 j의 start_time을 가져옴 이게 madi_end보다 크면 사용함
            # 현재 마디에서 가장 큰 노트를 찾는것임
            best_j: int | None = None
            best_diff: float = float("inf")

            j: int = i
            while j < note_lengh:
                note: BasicPitchNoteEventDTO = notes[j]
                ns: float = float(note.start_time)
                ne: float = float(note.end_time)

                if ns >= madi_end:
                    break

                is_active_at_bar_start: bool = ns <= madi_start < ne
                if is_active_at_bar_start:
                    best_j = j
                    best_diff = 0.0
                    break

                diff: float = abs(ns - madi_start)

                if diff < best_diff:
                    best_diff = diff
                    best_j = j
                elif ns > madi_start and diff > best_diff:
                    break

                j += 1

            if best_j is not None:
                root_pitch = int(notes[best_j].pitch_midi)
                root_conf = (
                    None
                    if notes[best_j].confidence is None
                    else float(notes[best_j].confidence)
                )

            # 마디에 노트가 없으면 스킵
            if root_pitch is None:
                continue

            # 마디를 beats_per_bar개의 beat로 채움
            for b in range(beats_per_bar):
                beat_start: float = madi_start + float(b) * one_bak_sec
                beat_end: float = beat_start + one_bak_sec

                # 전체 곡 범위를 넘어가면 중단
                if beat_start >= t_end:
                    break

                out.append(
                    BasicPitchNoteEventDTO(
                        start_time=float(beat_start),
                        end_time=float(beat_end),
                        pitch_midi=int(root_pitch),
                        confidence=root_conf,
                    )
                )

        return out

    def build_file(
        self,
        *,
        bpm: float,
        original_notes: list[BasicPitchNoteEventDTO],
        output_dir: str,
        params: OnsetFrameFuseParams,
        overwrite: bool
    ) -> None:
        out: list[BasicPitchNoteEventDTO] = self.build(
            bpm=bpm,
            original_notes=original_notes,
            params=params,
        )

        out_dir: Path = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path: Path = out_dir / self.output_filename

        payload: list[dict[str, Any]] = [
            {
                "start_time": float(n.start_time),
                "end_time": float(n.end_time),
                "pitch_midi": int(n.pitch_midi),
                "confidence": None if n.confidence is None else float(n.confidence),
            }
            for n in out
        ]
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")