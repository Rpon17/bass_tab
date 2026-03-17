from __future__ import annotations

from pathlib import Path

from app.adapters.tab.onset.onset_json_normalization_adapter import OnsetNormalizeAdapter
from app.application.ports.tab.onset.onset_json_noramization_port import OnsetNormalizeParams


def main() -> None:
    adapter: OnsetNormalizeAdapter = OnsetNormalizeAdapter()

    input_path: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001\onset_note_octave_normalized.json")
    output_dir: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001")

    params: OnsetNormalizeParams = OnsetNormalizeParams(
        merge_gap_seconds=0.01,
        pitch_merge_tolerance=0,
        min_note_seconds=0.05,
    )

    out_path: Path = adapter.normalize_file(
        input_json_path=input_path,
        output_json_dir=output_dir,
        params=params,
        overwrite=True,
    )

    print("done:", out_path)


if __name__ == "__main__":
    main()