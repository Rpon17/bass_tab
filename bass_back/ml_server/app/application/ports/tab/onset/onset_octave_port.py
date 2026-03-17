from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO


@dataclass(frozen=True)
class OnsetPitchOctaveNormalizeParams:
    alias_semitones: list[int]
        
    midi_min: int = 28
    midi_max: int = 70
    
    lambda_step: float = 0.15
    lambda_oct: float = 1.5
    
    alias_cost_per_octave: float = 3.0

    conf_floor: float = 0.1
    conf_power: float = 1.5
    conf_default: float = 0.3
    conf_cost: float = 0.8
    


class OnsetPitchOctaveNormalizePort(ABC):
    @abstractmethod
    def normalize(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: OnsetPitchOctaveNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        raise NotImplementedError

    @abstractmethod
    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_dir: Path,
        params: OnsetPitchOctaveNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        raise NotImplementedError