from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RootTabRequestPort:
    normalazed_note_events_json_path: Path
    output_dir:Path
    
@dataclass(frozen=True)
class RootTabResultPath:
    root_note_events_json_path: Path


class TabNormalizationUseCasePort(ABC):
    @abstractmethod
    async def original_tab_save(
        self,
        *,
        req: RootTabRequestPort,
    ) -> RootTabResultPath:
        ...