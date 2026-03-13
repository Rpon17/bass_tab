from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO


@dataclass(frozen=True)
class OnsetFrameFuseParams:
    beats_per_bar: int = 4  # 한 마디에 몇 beat(4/4면 4)
    steps_per_beat: int = 4  # 1 beat를 몇 step으로 나눌지(16분이면 4)
    quantize: bool = True # quantize 할지말지

    match_window_steps: int = 1  # onset<->frame 매칭 허용 오차(±steps)

    allow_octave_equiv: bool = True
    min_overlap_steps: float = 0.01 # 이거밖아 안겹치면 인정못한다

    missing_min_steps: int = 1  # onset이 측정 못했는데 프레임이 이거 이상유지되면 됨

    onset_bias: float = 1.1  # onset 우선 가중


class OnsetFrameFusePort(Protocol):
    def normalize(
        self,
        *,
        bpm: float,
        onset_notes: list[BasicPitchNoteEventDTO],
        frame_notes: list[BasicPitchNoteEventDTO],
        params: OnsetFrameFuseParams,
    ) -> list[BasicPitchNoteEventDTO]:
        ...

    def normalize_file(
        self,
        *,
        bpm: float,
        onset_notes: list[BasicPitchNoteEventDTO],
        frame_notes: list[BasicPitchNoteEventDTO],
        output_dir: str,
        params: OnsetFrameFuseParams,
    ) -> None:
        ...