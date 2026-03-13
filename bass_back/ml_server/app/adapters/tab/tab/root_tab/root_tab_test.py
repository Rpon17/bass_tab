from pathlib import Path
import json

from app.adapters.tab.tab.origianal_tab.candidate_adapter import BassTabCandidateBuilderAdapter
from app.adapters.tab.tab.root_tab.root_tab_adapter import RootTabGenerateAdapter
from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO


input_json_path: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001\root.json")

payload = json.loads(input_json_path.read_text(encoding="utf-8"))

notes: list[BasicPitchNoteEventDTO] = []
for item in payload:
    notes.append(
        BasicPitchNoteEventDTO(
            start_time=float(item["start_time"]),
            end_time=float(item["end_time"]),
            pitch_midi=int(item["pitch_midi"]),
            confidence=None if item.get("confidence") is None else float(item["confidence"]),
        )
    )

candidate_builder: BassTabCandidateBuilderAdapter = BassTabCandidateBuilderAdapter()

adapter: RootTabGenerateAdapter = RootTabGenerateAdapter(
    candidate_builder=candidate_builder,
)

output_path: Path = adapter.tab_generate(
    original_json=notes,
    bpm=212,
    output_dir=Path("C:/bass_project/storage/final/last"),
    asset_id="root_last",
)

print(f"done: {output_path}")