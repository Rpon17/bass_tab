from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.merge.original.onset_frame_plus_port import OnsetFrameFuseParams
from app.adapters.tab.merge.original.onset_frame_plus_adapter import (
   OnsetFrameFuseAdapter,
)


def _load_notes(*, path: Path) -> list[BasicPitchNoteEventDTO]:
    with path.open("r", encoding="utf-8") as f:
        payload: list[dict[str, Any]] = json.load(f)

    return [
        BasicPitchNoteEventDTO(
            start_time=float(d["start_time"]),
            end_time=float(d["end_time"]),
            pitch_midi=int(d["pitch_midi"]),
            confidence=None if d.get("confidence") is None else float(d["confidence"]),
        )
        for d in payload
    ]


if __name__ == "__main__":
    onset_path: Path = Path(
        r"C:\bass_project\storage\final\assets\test_asset_001\onset_note_normalization.json"
    )
    frame_path: Path = Path(
        r"C:\bass_project\storage\final\assets\test_asset_001\frame_note_normalize.json"
    )
    output_dir: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001")

    bpm: float = 212

    onset_notes: list[BasicPitchNoteEventDTO] = _load_notes(path=onset_path)
    frame_notes: list[BasicPitchNoteEventDTO] = _load_notes(path=frame_path)

    adapter: OnsetFrameFuseAdapter = OnsetFrameFuseAdapter()

    out_path: Path = adapter.normalize_file(
        bpm=212,
        onset_notes=onset_notes,
        frame_notes=frame_notes,
        output_dir=output_dir,
        overwrite=True,
        params=OnsetFrameFuseParams
    )

    print("done")