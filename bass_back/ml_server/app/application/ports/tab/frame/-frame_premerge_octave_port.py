from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchFramePitchDTO


@dataclass(frozen=True)
class FramePitchOctaveNormalizeParams:
    # pitch 최대 최소 
    midi_min: int = 28
    midi_max: int = 70

    # 옥타브 이동 
    alias_semitones: list[int] = (0, -12, 12)  # type: ignore[assignment]
    alias_cost_per_octave: float = 6.0 # 옥타브 이동에 대한 패널티 가중치

    # 연속성
    lambda_step: float = 0.25 # 연속프레임간 피치변화 가중치
    lambda_oct: float = 4.0 # 옥타브 이동시 가중치

    conf_floor: float = 0.1 # confidence 최소
    conf_power: float = 2.5 # 가중치 루트 2함
    conf_default: float = 0.4 # conf 비었을대 경우 
    conf_cost: float = 1.0 # conf 가중치
    
    premerge_sec : float = 0.2 # premerge한도
    unmerged_t : float = 0.1 # merge안되었을때 더하는 시간
    
    octave_close : float = 0.2 # 이보다 가까운데 음이 같거나 +-12면 튄거임
    
    
    def __post_init__(self) -> None:
        object.__setattr__(self, "alias_semitones", [int(x) for x in self.alias_semitones])

        if int(self.midi_max) < int(self.midi_min):
            raise ValueError("midi_max must be >= midi_min")
        if not self.alias_semitones:
            raise ValueError("alias_semitones must not be empty")


class FramePitchOctaveNormalizePort(ABC):
    @abstractmethod
    def normalize(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: FramePitchOctaveNormalizeParams,
    ) -> list[BasicPitchFramePitchDTO]:
        raise NotImplementedError

    @abstractmethod
    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_dir: Path,
        params: FramePitchOctaveNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        raise NotImplementedError