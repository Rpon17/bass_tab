from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.application.ports.basic_pitch_port import BasicPitchFramePitchDTO 


@dataclass(frozen=True)
class FramePitchOctaveNormalizeParams:

    midi_min: int = 28
    midi_max: int = 79
    
    # transition_cost
    lambda_step: float = 0.15 # pitch이동 가중치 
    lambda_oct: float = 1.50 # 옥타브 이동 가중치
    
    # emission_cost
    alias_semitones: tuple[int, ...] = (0, 12, -12) # 옥타브 튐 가능 후보들
    alias_cost_per_octave: float = 4.0 # 한 옥타브 이동당 추가 비용

    
    conf_floor: float = 0.08 # confidence 최소
    conf_power: float = 0.5 # 2만큼 루트 하겠다
    conf_default : float = 0.6 # 최소 가중치
    conf_cost : float = 0.9 # confidence 보정치

class FramePitchOctaveNormalizePort(ABC):
    @abstractmethod
    def normalize(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: FramePitchOctaveNormalizeParams,
    ) -> list[BasicPitchFramePitchDTO]:
        raise NotImplementedError