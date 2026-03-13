from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO


@dataclass(frozen=True)
class BassTabBarNoteDTO:
    time: float
    offset: float
    line: int
    fret: int


@dataclass(frozen=True)
class BassTabBarDTO:
    bar_index: int
    start_time: float
    end_time: float
    notes: list[BassTabBarNoteDTO]


class OriginalTabGeneratePort(ABC):
    @abstractmethod
    def tab_generate(
        self,
        *,
        original_json: list[BasicPitchNoteEventDTO],
        bpm: int,
        output_dir: Path,
        asset_id: str,
    ) -> Path:
        raise NotImplementedError