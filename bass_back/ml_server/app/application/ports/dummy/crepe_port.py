# app/application/ports/crepe_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class CrepeParams:
    # I/O
    input_wav_path: Path
    output_dir: Path
    asset_id: str

    # output naming
    output_subdir: str = "crepe"
    output_filename: str = "crepe_frame_pitch.json"

    # CREPE inference
    model_capacity: Literal["tiny", "small", "medium", "large", "full"] = "small"
    step_size_ms: int = 10
    use_viterbi: bool = True

    # preprocessing
    target_sr: int = 16000
    mono: bool = True

    # post filtering
    conf_threshold: float = 0.1
    return_unvoiced_as_none: bool = True

    # debug
    debug_save_csv: bool = True
    debug_save_npz: bool = False


class CrepePort(ABC):
    @abstractmethod
    async def export_frame_pitch(self, *, params: CrepeParams) -> Path:
        raise NotImplementedError