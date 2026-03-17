from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.tab.original_tab.candidate_port import (
    BassTabCandidateDTO,
)


@dataclass(frozen=True)
class BassTabViterbiStepDTO:
    note_index: int
    pitch_midi: int
    start_time: float
    end_time: float
    line: int
    fret: int


@dataclass(frozen=True)
class BassTabViterbiParams:
    string_change_cost: float = 5.0
    fret_move_cost: float = 1.0

    same_string_far_move_cost: float = 3.0
    same_string_far_move_start: int = 7

    fret_height_2_cost: float = 0.5
    fret_height_3_cost: float = 1.5
    fret_height_4_cost: float = 3.0

    open_string_cost: float = 0.0

    local_string_bonus: float = -6.0
    local_window_bar_count: int = 4

    string_zigzag_cost: float = 6.0
    string_cut_t_beats: float = 0.5

    sufficient_t_beats: float = 1.5
    low_fret_bias_cost: float = 0.2


class BassTabViterbiPort(ABC):
    @abstractmethod
    def decode(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        candidates: list[list[BassTabCandidateDTO]],
        bpm: int,
        params: BassTabViterbiParams,
    ) -> list[BassTabViterbiStepDTO]:
        """
        candidate sequence에 대해 Viterbi 기반으로 최적의 line/fret 경로를 선택한다.
        """
        raise NotImplementedError