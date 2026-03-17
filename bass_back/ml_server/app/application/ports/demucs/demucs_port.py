from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DemucsDspParams:
    enable_dsp: bool = True
    dsp_highpass_hz: float = 40.0
    dsp_lowpass_hz: float = 4500.0
    dsp_force_mono: bool = True
    dsp_compress: bool = True


@dataclass(frozen=True)
class DemucsSplitSetting:
    boosted_volume_db: float = 10.0
    demucs_model: str = "htdemucs_ft"
    overwrite_outputs: bool = True
    cleanup_stems: bool = True


class DemucsPort(ABC):
    @abstractmethod
    async def split(
        self,
        *,
        input_wav_path: Path,
        output_dir: Path,
        asset_id: str,
        setting: DemucsSplitSetting,
        params: DemucsDspParams,
    ) -> Path: # bass_only.wav
        raise NotImplementedError

    @abstractmethod
    async def split_file(
        self,
        *,
        input_wav_path: Path,
        output_dir: Path,
        asset_id: str,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> None:
        raise NotImplementedError