from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
class BpmEstimatePort(ABC):
    @abstractmethod
    async def estimate_bpm(
        self,
        *,
        input_audio_path: Path,
        input_json_path: list[BasicPitchNoteEventDTO],
        start_seconds: float = 0.0,
        duration_seconds: float | None = None,
        sr: int = 22050,
        
    ) -> int:
        raise NotImplementedError
    
    @abstractmethod
    async def estimat_bpm_file(
        self,
        *,
        input_wav_path: Path,
        input_json_path: Path,
        start_seconds: float = 0.0,
        duration_seconds: float | None = None,
        sr: int = 22050,
    ) -> None:
        raise NotImplementedError
    
@dataclass
class BpmEstimateAdapterConfig:
    hop_length: int = 512
    min_bpm: float = 40.0
    max_bpm: float = 240.0
    round_mode: str = "round"


    use_hpss: bool = True   # 타격성 부분만 남김 
    use_multiband_onset: bool = True    # 여러 주파수 부분에서 onset을 계산해서 합침 
    use_candidate: bool = True # *2 같은 후보들 사용
    onset_aggregate: str = "median" # 멀티밴드 onset을 어떻게 합칠지
    

