from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


class BpmEstimationError(RuntimeError):
    pass


@dataclass(frozen=True)
class BpmEstimateDomain:
    bpm: float
    confidence: float  
    offset_seconds: float  
    beat_times: Sequence[float] 
