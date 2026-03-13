from __future__ import annotations

from pathlib import Path

from app.adapters.tab.frame.frame_json_normalization_adapter import FramePitchNormalizeAdapter
from app.application.ports.tab.frame.frame_note_normalization_port import FramePitchNormalizeParams


def main() -> None:
    input_json_path: Path = Path(
        r"C:\bass_project\storage\final\assets\test_asset_001\frame_pitch_octave_normalized.json"
    )

    # ✅ 출력: output_dir/assets/{asset_id}/frame_note_normalize.json
    output_dir: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001")

    adapter: FramePitchNormalizeAdapter = FramePitchNormalizeAdapter()

    params: FramePitchNormalizeParams = FramePitchNormalizeParams()

    
    adapter.normalize_file(
        input_json_path=input_json_path,
        output_dir=output_dir,
        params=params,
        overwrite=True,
    )

    print("done")


if __name__ == "__main__":
    main()