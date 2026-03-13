from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO



@dataclass(frozen=True)
class BassTabCandidateDTO:
    line: int
    fret: int
    is_open: bool # 개방현인지 
    fret_height: int #  1이면 0~5 2이면 6~11 3이면 12~16 4이면 17이상


# 나중에 candidate pitch들 계산용
@dataclass(frozen=True)
class BassStringTuningDTO:
    line: int
    open_pitch: int


# 
@dataclass(frozen=True)
class BassTabCandidateBuildParams:
    min_fret: int = 0
    max_fret: int = 24
    tuning: tuple[BassStringTuningDTO, ...] = field(
        default_factory=lambda: (
            BassStringTuningDTO(line=4, open_pitch=28),
            BassStringTuningDTO(line=3, open_pitch=33),
            BassStringTuningDTO(line=2, open_pitch=38),
            BassStringTuningDTO(line=1, open_pitch=43),
        )
    )
    
"""  
index	line	open_pitch
0	    4	    28
1	    3	    33
2	    2	    38
3	    1	    43
"""

class BassTabCandidateBuilderPort(ABC):
    @abstractmethod
    def build_candidates(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: BassTabCandidateBuildParams,
    ) -> list[list[BassTabCandidateDTO]]:
        raise NotImplementedError