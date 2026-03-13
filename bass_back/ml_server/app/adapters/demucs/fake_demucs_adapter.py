from __future__ import annotations

import asyncio
import shutil
import wave
from dataclasses import dataclass
from pathlib import Path

from app.application.ports.demucs.demucs_port import (
    DemucsDspParams,
    DemucsPort,
    DemucsSplitSetting,
)


@dataclass(frozen=True)
class FakeDemucsAdapter(DemucsPort):
    fake_delay_seconds: float = 0.0

    async def split(
        self,
        *,
        input_wav_path: Path,
        output_dir: Path,
        asset_id: str,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> Path:
        await self.split_file(
            input_wav_path=input_wav_path,
            output_dir=output_dir,
            asset_id=asset_id,
            setting=setting,
            dsp=dsp,
        )
        return output_dir / "audio" / "bass_only.wav"

    async def split_file(
        self,
        *,
        input_wav_path: Path,
        output_dir: Path,
        asset_id: str,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> None:
        if not input_wav_path.exists():
            raise FileNotFoundError(f"input wav not found: {input_wav_path}")

        if input_wav_path.suffix.lower() != ".wav":
            raise ValueError(f"expected .wav input, got: {input_wav_path}")

        if self.fake_delay_seconds > 0.0:
            await asyncio.sleep(self.fake_delay_seconds)

        audio_dir: Path = output_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        original_copy_path: Path = audio_dir / "original.wav"
        bass_only_path: Path = audio_dir / "bass_only.wav"
        bass_boosted_path: Path = audio_dir / "bass_boosted.wav"
        bass_removed_path: Path = audio_dir / "bass_removed.wav"

        shutil.copy2(input_wav_path, original_copy_path)
        shutil.copy2(input_wav_path, bass_only_path)
        shutil.copy2(input_wav_path, bass_boosted_path)
        shutil.copy2(input_wav_path, bass_removed_path)

        self._validate_wav(original_copy_path)
        self._validate_wav(bass_only_path)
        self._validate_wav(bass_boosted_path)
        self._validate_wav(bass_removed_path)

    def _validate_wav(self, wav_path: Path) -> None:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels: int = int(wf.getnchannels())
            sample_width: int = int(wf.getsampwidth())
            frame_rate: int = int(wf.getframerate())
            n_frames: int = int(wf.getnframes())

        if n_channels <= 0:
            raise ValueError(f"invalid wav channels: {wav_path}")
        if sample_width <= 0:
            raise ValueError(f"invalid wav sample width: {wav_path}")
        if frame_rate <= 0:
            raise ValueError(f"invalid wav sample rate: {wav_path}")
        if n_frames <= 0:
            raise ValueError(f"empty wav data: {wav_path}")