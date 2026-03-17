from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.application.ports.basic_pitch.basic_pitch_port import (
    BasicPitchFramePitchDTO,
    BasicPitchNoteEventDTO,
)


@dataclass(frozen=True)
class FramePitchNormalizeParams:
    merge_gap_seconds: float = 0.012
    min_note_seconds: float = 0.001

    conf_threshold: float = 0.40
    drop_if_no_low_conf: bool = True

    octave_shift_semitones: int = 12

    default_plus_time: float = 0.001
    maximum_divide_time: float = 0.012

    fast_jump_sec: float = 0.25
    fast_jump_semitones: int = 9
    snap_only_octave: bool = False
    
    midi_min : int = 28
    midi_max : int = 70
    
    default : int = 28
class FramePitchNormalizePort(ABC):
    @abstractmethod
    def normalize(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: FramePitchNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        raise NotImplementedError

    @abstractmethod
    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_dir: Path,
        params: FramePitchNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        raise NotImplementedError