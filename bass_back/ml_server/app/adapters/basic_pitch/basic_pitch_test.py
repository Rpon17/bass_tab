from __future__ import annotations

import asyncio
from pathlib import Path

from app.adapters.basic_pitch.basic_pitch_adapter import BasicPitchAdapter
from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchParams


async def main() -> None:
    adapter: BasicPitchAdapter = BasicPitchAdapter()

    params: BasicPitchParams = BasicPitchParams(
        input_wav_path=Path(
            r"C:\bass_project\storage\demucs\asset\test_asset_001\audio\bass_only.wav"
        ),
        output_dir=Path(
            r"C:\bass_project\storage"
        ),
        asset_id="last",
        frame_conf_threshold=0.3,
        note_events_filename="note_events.json",
        frame_pitches_filename="frame_pitches.json",
    )

    result = await adapter.export_file(params=params)

    print("done")
    print(result.note_events_json_path)
    print(result.frame_pitches_json_path)


if __name__ == "__main__":
    asyncio.run(main())