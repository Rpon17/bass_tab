from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from pathlib import Path

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.merge.original.onset_frame_plus_port import OnsetFrameFuseParams

class RootTabBuildPort(Protocol):

    def build(
        self,
        *,
        bpm: float,
        original_notes: list[BasicPitchNoteEventDTO],
        output_dir : Path,
        asset_id : str,
        params: OnsetFrameFuseParams,
    ) -> None:
        raise NotImplementedError

    def build_file(
        self,
        *,
        bpm: float,
        original_notes: list[BasicPitchNoteEventDTO],
        output_dir: str,
        params: OnsetFrameFuseParams,
    ) -> None:
        raise NotImplementedError