from __future__ import annotations

from pathlib import Path

from app.adapters.tab.frame.frame_octave_adapter import FramePitchOctaveNormalizeAdapter
from app.application.ports.tab.frame.frame_octave_port import FramePitchOctaveNormalizeParams


def main() -> None:
    input_json_path: Path = Path(r"C:\bass_project\storage\assets\last\frame_pitches.json")
    output_dir: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001")

    params: FramePitchOctaveNormalizeParams = FramePitchOctaveNormalizeParams()
    adapter: FramePitchOctaveNormalizeAdapter = FramePitchOctaveNormalizeAdapter()

    out_path: Path = adapter.normalize_file(
        input_json_path=input_json_path,
        output_dir=output_dir,
        params=params,
        overwrite=True,
    )

    print("frame_octave 보정 종료")
    print("output:", out_path)


if __name__ == "__main__":
    main()