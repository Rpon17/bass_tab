from __future__ import annotations

import asyncio
from pathlib import Path

from app.adapters.spleeter.spleeter_split_adapter import SpleeterAdapter
from app.application.ports.spleeter_port import SpleeterPort


async def main() -> None:
    adapter: SpleeterPort = SpleeterAdapter()

    input_wav_path: Path = Path(
        r"C:\bass_project\storage\songs\c422012dd22046ab95f91e537d59be1a\results\90b97c8940ef4dc1af030140ebb1b691\audio\original.mp3"
    )

    output_dir: Path = Path(
        r"C:\bass_project\storage\songs\spleeter"
    )

    await adapter.split(
        input_wav_path=input_wav_path,
        output_dir=output_dir,
        asset_id = "1"
    )

    print("✅ Spleeter split finished")


if __name__ == "__main__":
    asyncio.run(main())
