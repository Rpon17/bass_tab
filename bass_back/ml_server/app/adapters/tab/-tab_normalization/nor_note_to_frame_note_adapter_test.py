from __future__ import annotations

import json
from pathlib import Path

from app.application.ports.nor_note_to_frame_note_port import (
    NoteEvent,
    FrameLabels,
)
from app.adapters.tab.tab_normalization.nor_note_to_frame_note_adapter import (
    note_events_to_frame_labels,
    save_frame_labels_json,
)


def main() -> None:
    input_path: Path = Path(r"C:\bass_project\storage\test4\note_events.normalized.json")
    output_dir: Path = Path(r"C:\bass_project\storage\nor_to_fra\test4")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) load json (list[dict])
    raw: list[dict] = json.loads(input_path.read_text(encoding="utf-8"))

    # 2) parse -> NoteEvent
    note_events: list[NoteEvent] = [
        NoteEvent(
            onset_sec=float(d["onset_sec"]),
            offset_sec=float(d["offset_sec"]),
            pitch_midi=int(d["pitch_midi"]),
            confidence=float(d.get("confidence", 0.0)),
        )
        for d in raw
    ]

    # 3) convert -> FrameLabels
    labels: FrameLabels = note_events_to_frame_labels(
        note_events=note_events,
        frame_hz=100.0,
        midi_min=28,
        midi_max=80,
        num_frames=None,
    )

    # 4) save
    out_path: Path = output_dir / "frame_labels.json"
    save_frame_labels_json(out_path=out_path, labels=labels)

    print(f"OK: saved {out_path}")


if __name__ == "__main__":
    main()
