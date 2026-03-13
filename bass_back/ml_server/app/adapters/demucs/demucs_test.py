from __future__ import annotations

import asyncio
from pathlib import Path

from app.adapters.demucs.demucs_adapter import DemucsAdapter
from app.application.ports.demucs.demucs_port import DemucsDspParams, DemucsSplitSetting


async def main() -> None:
    adapter: DemucsAdapter = DemucsAdapter()

    input_wav_path: Path = Path(
        r"C:\bass_project\storage\songs\c422012dd22046ab95f91e537d59be1a\results\90b97c8940ef4dc1af030140ebb1b691\audio\original.mp3"
    )

    output_dir: Path = Path(r"C:\bass_project\storage\demucs")
    asset_id: str = "test_asset_001"

    split_setting: DemucsSplitSetting = DemucsSplitSetting(
        boosted_volume_db=10.0,
        demucs_model="htdemucs",
        overwrite_outputs=True,
        cleanup_stems=True,
    )

    # DSP를 켜고 싶으면 enable_dsp=True로
    params: DemucsDspParams = DemucsDspParams(
        enable_dsp=False,
        dsp_highpass_hz=40.0,
        dsp_lowpass_hz=5000.0,
        dsp_force_mono=True,
        dsp_compress=True,
    )

    out_bass_only: Path = await adapter.split_full(
        input_wav_path=input_wav_path,
        output_dir=output_dir,
        asset_id=asset_id,
        split_setting=split_setting,
        params=params,
    )

    print("Demucs split finished")
    print("bass_only:", out_bass_only)

    audio_dir: Path = output_dir / "asset" / asset_id / "audio"
    print("📁 audio_dir:", audio_dir)

    expected_files: list[str] = [
        "original.wav",
        "bass_only.wav",
        "bass_removed.wav",
        "bass_boosted.wav",
    ]
    for name in expected_files:
        p: Path = audio_dir / name
        print(f" - {name}: {'OK' if p.exists() else 'MISSING'} ({p})")


if __name__ == "__main__":
    asyncio.run(main())