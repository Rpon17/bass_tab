from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.application.ports.basic_pitch_port import BasicPitchFramePitchDTO , BasicPitchNoteEventDTO


@dataclass(frozen=True)
class FramePitchNormalizeParams:
    merge_gap_seconds: float = 0.001
    min_note_seconds: float = 0.0012
    low_pitch_threshold: int = 40
    octave_shift_semitones: int = 12
    conf_threshold: float = 0.40
    drop_if_no_low_conf: bool = True
    
    default_plus_time = float = 0.001
    maximum_divide_time = float = 0.012

class FramePitchNormalizePort(ABC):
    @abstractmethod
    def normalize(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: FramePitchNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        raise NotImplementedError