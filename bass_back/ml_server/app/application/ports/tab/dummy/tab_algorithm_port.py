from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

# 요청받는 dto
@dataclass(frozen=True)
class AlphaTabRequestPort:
    bpm: float
    note_events_json_path: Path 
    output_dir: Path
    asset_id: str
    norm_title: str
    norm_artist: str
    
    # 락은 4분의 4박자.
    time_signature_numerator: int = 4
    time_signature_denominator: int = 4

# 내보내는 dto
@dataclass(frozen=True)
class AlphaTabdResultPort:
    alphatab_json_path: Path

# 결과적으로 이게 포트
class AlphaTabPort(ABC):
    @abstractmethod
    async def build_and_save(
        self,
        *,
        req: AlphaTabRequestPort,
    ) -> AlphaTabdResultPort:
        ...
