from __future__ import annotations

from pathlib import Path

from app.application.ports.tab.onset.onset_octave_port import OnsetPitchOctaveNormalizeParams
from app.adapters.tab.onset.onset_octave_adapter import OnsetPitchOctaveNormalizeAdapter


def main() -> None:
    input_path: Path = Path(r"C:\bass_project\storage\assets\last\note_events.json")
    output_dir: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001")

    params: OnsetPitchOctaveNormalizeParams = OnsetPitchOctaveNormalizeParams(
        alias_semitones=[-24, -12, 0, 12, 24],
    )

    adapter: OnsetPitchOctaveNormalizeAdapter = OnsetPitchOctaveNormalizeAdapter()

    out_path: Path = adapter.normalize_file(
        input_json_path=input_path,
        output_dir=output_dir,
        params=params,
        overwrite=True,
    )

    print(f"done: {out_path}")


if __name__ == "__main__":
    main()