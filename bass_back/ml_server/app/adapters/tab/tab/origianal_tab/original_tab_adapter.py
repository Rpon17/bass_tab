from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.tab.original_tab.candidate_port import (
    BassTabCandidateBuildParams,
    BassTabCandidateBuilderPort,
    BassTabCandidateDTO,
)
from app.application.ports.tab.tab.original_tab.original_tab_port import (
    BassTabBarDTO,
    BassTabBarNoteDTO,
    OriginalTabGeneratePort,
)
from app.application.ports.tab.tab.original_tab.viterbi_port import (
    BassTabViterbiParams,
    BassTabViterbiPort,
    BassTabViterbiStepDTO,
)


@dataclass(frozen=True)
class OriginalTabGenerateAdapter(OriginalTabGeneratePort):
    candidate_builder: BassTabCandidateBuilderPort
    viterbi: BassTabViterbiPort
    output_filename: str = "original_tab.json"

    beats_per_bar: int = 4
    candidate_params: BassTabCandidateBuildParams = field(
        default_factory=BassTabCandidateBuildParams
    )
    viterbi_params: BassTabViterbiParams = field(
        default_factory=BassTabViterbiParams
    )

    def tab_generate(
        self,
        *,
        original_json: list[BasicPitchNoteEventDTO],
        bpm: int,
        output_dir: Path,
        asset_id: str,
    ) -> Path:
        if bpm <= 0:
            raise ValueError("bpm must be > 0")
        if self.beats_per_bar <= 0:
            raise ValueError("beats_per_bar must be > 0")

        filtered_notes: list[BasicPitchNoteEventDTO] = self._filter_notes(notes=original_json)

        original_tab_path: Path = self._build_output_path(
            output_dir=output_dir,
            asset_id=asset_id,
        )

        if not filtered_notes:
            self._write_json(
                output_path=original_tab_path,
                bars=[],
            )
            return original_tab_path

        sorted_notes: list[BasicPitchNoteEventDTO] = sorted(
            filtered_notes,
            key=lambda x: (float(x.start_time), float(x.end_time), int(x.pitch_midi)),
        )

        raw_candidates: list[list[BassTabCandidateDTO]] = self.candidate_builder.build_candidates(
            notes=sorted_notes,
            params=self.candidate_params,
        )

        valid_notes: list[BasicPitchNoteEventDTO] = []
        valid_candidates: list[list[BassTabCandidateDTO]] = []
        skipped_count: int = 0

        for i, one_candidates in enumerate(raw_candidates):
            if not one_candidates:
                note: BasicPitchNoteEventDTO = sorted_notes[i]
                skipped_count += 1
                print(
                    f"[SKIP NO CANDIDATE] idx={i} "
                    f"pitch={int(note.pitch_midi)} "
                    f"start={float(note.start_time)} "
                    f"end={float(note.end_time)}"
                )
                continue

            valid_notes.append(sorted_notes[i])
            valid_candidates.append(one_candidates)

        if skipped_count > 0:
            print(f"[TAB GENERATE] skipped_no_candidate={skipped_count}")

        if not valid_notes:
            self._write_json(
                output_path=original_tab_path,
                bars=[],
            )
            return original_tab_path

        steps: list[BassTabViterbiStepDTO] = self.viterbi.decode(
            notes=valid_notes,
            candidates=valid_candidates,
            bpm=int(bpm),
            params=self.viterbi_params,
        )

        bars: list[BassTabBarDTO] = self._group_steps_by_bar(
            steps=steps,
            bpm=int(bpm),
            beats_per_bar=int(self.beats_per_bar),
        )

        self._write_json(
            output_path=original_tab_path,
            bars=bars,
        )
        return original_tab_path

    def _filter_notes(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
    ) -> list[BasicPitchNoteEventDTO]:
        out: list[BasicPitchNoteEventDTO] = []
        for note in notes:
            start_time: float = float(note.start_time)
            end_time: float = float(note.end_time)
            if end_time <= start_time:
                continue
            out.append(note)
        return out

    def _group_steps_by_bar(
        self,
        *,
        steps: list[BassTabViterbiStepDTO],
        bpm: int,
        beats_per_bar: int,
    ) -> list[BassTabBarDTO]:
        if not steps:
            return []
        if bpm <= 0:
            raise ValueError("bpm must be > 0")
        if beats_per_bar <= 0:
            raise ValueError("beats_per_bar must be > 0")

        seconds_per_beat: float = 60.0 / float(bpm)
        bar_seconds: float = seconds_per_beat * float(beats_per_bar)

        bars_map: dict[int, list[BassTabBarNoteDTO]] = {}

        for step in steps:
            time: float = float(step.start_time)
            bar_index: int = int(time // bar_seconds)
            bar_start_time: float = float(bar_index) * bar_seconds
            offset: float = (time - bar_start_time) / seconds_per_beat

            note_dto: BassTabBarNoteDTO = BassTabBarNoteDTO(
                time=time,
                offset=offset,
                line=int(step.line),
                fret=int(step.fret),
            )

            if bar_index not in bars_map:
                bars_map[bar_index] = []
            bars_map[bar_index].append(note_dto)

        out: list[BassTabBarDTO] = []
        for bar_index in sorted(bars_map.keys()):
            bar_start_time: float = float(bar_index) * bar_seconds
            bar_end_time: float = bar_start_time + bar_seconds
            notes_in_bar: list[BassTabBarNoteDTO] = sorted(
                bars_map[bar_index],
                key=lambda x: (float(x.time), float(x.offset), int(x.line), int(x.fret)),
            )

            out.append(
                BassTabBarDTO(
                    bar_index=bar_index,
                    start_time=bar_start_time,
                    end_time=bar_end_time,
                    notes=notes_in_bar,
                )
            )

        return out

    def _build_output_path(
        self,
        *,
        output_dir: Path,
        asset_id: str,
    ) -> Path:
        asset_dir: Path = Path(output_dir) / "asset" / str(asset_id)
        tab_dir: Path = asset_dir / "tab"
        tab_dir.mkdir(parents=True, exist_ok=True)
        return tab_dir / self.output_filename

    def _write_json(
        self,
        *,
        output_path: Path,
        bars: list[BassTabBarDTO],
    ) -> None:
        payload: list[dict[str, object]] = []
        for bar in bars:
            payload.append(
                {
                    "bar_index": int(bar.bar_index),
                    "start_time": float(bar.start_time),
                    "end_time": float(bar.end_time),
                    "notes": [
                        {
                            "time": float(note.time),
                            "offset": float(note.offset),
                            "line": int(note.line),
                            "fret": int(note.fret),
                        }
                        for note in bar.notes
                    ],
                }
            )

        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )