from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.merge.original.onset_frame_plus_port import OnsetFrameFuseParams

from app.adapters.tab.merge.root.root_note_adapter import RootTabBuildAdapter

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
    params=OnsetFrameFuseParams(
    beats_per_bar=4,
    steps_per_beat=4,
    )
    
    original_notes: Path = Path(
        r"C:\bass_project\storage\final\assets\test_asset_001\real_original.json"
    )
    output_dir: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001")

    bpm: float = 212

    original_notes: list[BasicPitchNoteEventDTO] = _load_notes(path=original_notes)

    adapter: RootTabBuildAdapter =RootTabBuildAdapter()

    adapter.build_file(
        bpm=212,
        original_notes=original_notes,
        output_dir=output_dir,
        overwrite=True,
        params=OnsetFrameFuseParams
    )

    print("done")