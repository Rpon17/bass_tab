from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO


@dataclass(frozen=True)
class OnsetNormalizeParams:
    grid_seconds: Optional[float] = None
    merge_gap_seconds: float = 0.05
    pitch_merge_tolerance: int = 0
    min_note_seconds: Optional[float] = None
    min_start_gap_seconds = 0.001 
    
    alias_semitones: list[int] = (0, -12, 12)  # type: ignore[assignment]

    midi_min: int = 28
    midi_max: int = 72

    conf_floor: float = 0.10
    conf_power: float = 2.0
    conf_default: float = 1.0
    conf_cost: float = 1.0
    conf_threshold: float = 0.35
    
    alias_cost_per_octave: float = 1.0

    lambda_step: float = 0.05
    lambda_oct: float = 0.25
    
    fast_jump_sec: float = 0.25
    fast_jump_semitones: int = 9
    snap_only_octave: bool = False
    
    midi_min : int = 28
    midi_max : int = 70
    
    default : int = 28


class OnsetNormalizePort(ABC):
    @abstractmethod
    def normalize(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: OnsetNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        raise NotImplementedError

    @abstractmethod
    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_json_path: Path,
        params: OnsetNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        raise NotImplementedError