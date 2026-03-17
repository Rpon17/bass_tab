from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

# 정규화하는 포트
@dataclass(frozen=True)
class TabNormalizationPort:
    note_events_json_path: Path
    output_dir:Path
    
@dataclass(frozen=True)
class TabNormalizationResultPort:
    normalized_note_events_json_path: Path


class TabNormalizationUseCasePort(ABC):
    @abstractmethod
    async def normalize_and_save(
        self,
        *,
        req: TabNormalizationPort,
    ) -> TabNormalizationResultPort:
        ...