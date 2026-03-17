from __future__ import annotations

import asyncio
from pathlib import Path

from app.adapters.demucs.demucs_adapter import DemucsAdapter
from app.application.ports.demucs.demucs_port import (
    DemucsSplitSetting,
    DemucsDspParams,
)


async def main() -> None:
    adapter: DemucsAdapter = DemucsAdapter()

    input_wav_path: Path = Path(
        r"C:\bass_project\storage\demucs\asset\test_asset_001\audio\original.wav"  # ← 실제 테스트 wav 경로로 수정
    )

    output_dir: Path = Path(
        r"C:\bass_project\storage\demucs_test_output"
    )

    asset_id: str = "test_1"

    split_setting: DemucsSplitSetting = DemucsSplitSetting(
        boosted_volume_db=8.0,
        demucs_model="htdemucs",
        overwrite_outputs=True,
        cleanup_stems=True,
    )

    dsp_params: DemucsDspParams = DemucsDspParams(
        enable_dsp=True,
        dsp_highpass_hz=35.0,
        dsp_lowpass_hz=5000.0,
        dsp_force_mono=False,
        dsp_compress=True,
    )

    await adapter.split_file(
        input_wav_path=input_wav_path,
        output_dir=output_dir,
        asset_id=asset_id,
        split_setting=split_setting,
        params=dsp_params,
    )

    expected_output: Path = (
        output_dir / "asset" / asset_id / "audio" / "bass_only.wav"
    )

    if not expected_output.exists():
        raise RuntimeError("❌ bass_only.wav 생성 실패")

    print("✅ split_file 테스트 성공")
    print(f"📁 output: {expected_output}")


if __name__ == "__main__":
    asyncio.run(main())