from pathlib import Path
import json

from app.adapters.tab.tab.origianal_tab.candidate_adapter import BassTabCandidateBuilderAdapter
from app.adapters.tab.tab.origianal_tab.viterbi_adapter import BassTabViterbiAdapter
from app.adapters.tab.tab.origianal_tab.original_tab_adapter import OriginalTabGenerateAdapter
from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO


input_json_path: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001\real_original.json")

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
viterbi: BassTabViterbiAdapter = BassTabViterbiAdapter()

adapter: OriginalTabGenerateAdapter = OriginalTabGenerateAdapter(
    candidate_builder=candidate_builder,
    viterbi=viterbi,
)

output_path: Path = adapter.tab_generate(
    original_json=notes,
    bpm=212,
    output_dir=Path("C:/bass_project/storage/final/last"),
    asset_id="real_last",
)

print(f"done: {output_path}")