from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BasicPitchNoteEventDTO:
    start_time: float
    end_time: float
    pitch_midi: int
    confidence: float | None = None


@dataclass(frozen=True)
class BasicPitchFramePitchDTO:
    t: float
    pitch_midi: int
    confidence: float | None = None


@dataclass(frozen=True)
class BasicPitchParams:
    input_wav_path: Path
    output_dir: Path
    asset_id: str
    note_events_filename: str = "note_events.json"
    frame_pitches_filename: str = "frame_pitches.json"
    overwrite: bool = True
    frame_conf_threshold: float = 0.3
    frame_source: str = "notes"


@dataclass(frozen=True)
class BasicPitchResult:
    note_events_json_path: Path
    frame_pitches_json_path: Path


class BasicPitchPort(ABC):
    @abstractmethod
    async def export_onset(
        self,
        *,
        params: BasicPitchParams,
    ) -> list[BasicPitchNoteEventDTO]:
        raise NotImplementedError

    @abstractmethod
    async def export_frame(
        self,
        *,
        params: BasicPitchParams,
    ) -> list[BasicPitchFramePitchDTO]:
        raise NotImplementedError

    @abstractmethod
    async def export_file(
        self,
        *,
        params: BasicPitchParams,
    ) -> BasicPitchResult:
        raise NotImplementedError