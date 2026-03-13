from __future__ import annotations

import json
from pathlib import Path

from app.application.ports.tab.frame.frame_premerge_octave_port import FramePitchOctaveNormalizeParams
from app.adapters.tab.frame.frame_premerge_octave_adapter import FramePitchOctaveNormalizeAdapter


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

    print("[OK] premerge saved to:", out_path)

    with out_path.open("r", encoding="utf-8") as f:
        obj: object = json.load(f)

    if isinstance(obj, list):
        print("rows:", len(obj))
        if len(obj) > 0 and isinstance(obj[0], dict):
            print("first:", obj[0])
        if len(obj) > 1 and isinstance(obj[-1], dict):
            print("last:", obj[-1])
    else:
        print("unexpected json type:", type(obj))


if __name__ == "__main__":
    main()