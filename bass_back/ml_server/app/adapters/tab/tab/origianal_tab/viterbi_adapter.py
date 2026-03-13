from __future__ import annotations

from dataclasses import dataclass
from math import inf

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.tab.original_tab.candidate_port import BassTabCandidateDTO
from app.application.ports.tab.tab.original_tab.viterbi_port import (
    BassTabViterbiParams,
    BassTabViterbiPort,
    BassTabViterbiStepDTO,
)


@dataclass(frozen=True)
class BassTabViterbiAdapter(BassTabViterbiPort):
    """
    First-order Viterbi decoder with bass-oriented playability costs.

    방향:
    - DP는 1차 전이만 사용해서 안정적으로 유지
    - string change, fret move, same-string large jump, fret range,
      time 여유 시 low fret bias를 반영
    - 짧은 ABA zigzag는 후처리 smoothing에서 보정
    """

    def decode(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        candidates: list[list[BassTabCandidateDTO]],
        bpm: int,
        params: BassTabViterbiParams,
    ) -> list[BassTabViterbiStepDTO]:
        n_notes: int = len(notes)
        if n_notes == 0:
            return []
        if bpm <= 0:
            raise ValueError("bpm must be > 0")
        if n_notes != len(candidates):
            raise ValueError("notes length and candidates length must match")

        for i, one_candidates in enumerate(candidates):
            if not one_candidates:
                raise ValueError(f"note index {i} has no candidates")

        prev_costs: list[float] = [inf] * len(candidates[0])
        back_ptr: list[list[int]] = [
            [-1 for _ in range(len(candidates[i]))] for i in range(n_notes)
        ]

        first_preferred_line: int | None = self._get_local_preferred_line(
            notes=notes,
            current_index=0,
            bpm=bpm,
            local_window_bar_count=int(params.local_window_bar_count),
        )
        for s_idx, cand in enumerate(candidates[0]):
            prev_costs[s_idx] = self._emission_cost(
                candidate=cand,
                preferred_line=first_preferred_line,
                params=params,
            )

        for i in range(1, n_notes):
            cur_candidates: list[BassTabCandidateDTO] = candidates[i]
            prev_candidates: list[BassTabCandidateDTO] = candidates[i - 1]
            cur_costs: list[float] = [inf] * len(cur_candidates)

            preferred_line: int | None = self._get_local_preferred_line(
                notes=notes,
                current_index=i,
                bpm=bpm,
                local_window_bar_count=int(params.local_window_bar_count),
            )

            for cur_idx, cur_cand in enumerate(cur_candidates):
                emit_cost: float = self._emission_cost(
                    candidate=cur_cand,
                    preferred_line=preferred_line,
                    params=params,
                )

                best_cost: float = inf
                best_prev_idx: int = -1

                for prev_idx, prev_cand in enumerate(prev_candidates):
                    trans_cost: float = self._transition_cost(
                        notes=notes,
                        note_index=i,
                        prev_candidate=prev_cand,
                        cur_candidate=cur_cand,
                        bpm=bpm,
                        params=params,
                    )
                    total_cost: float = prev_costs[prev_idx] + emit_cost + trans_cost
                    if total_cost < best_cost:
                        best_cost = total_cost
                        best_prev_idx = prev_idx

                cur_costs[cur_idx] = best_cost
                back_ptr[i][cur_idx] = best_prev_idx

            prev_costs = cur_costs

        chosen_indices: list[int] = self._traceback(
            back_ptr=back_ptr,
            last_best_idx=self._argmin(values=prev_costs),
        )
        chosen_indices = self._smooth_short_zigzags(
            notes=notes,
            candidates=candidates,
            chosen_indices=chosen_indices,
            bpm=bpm,
            params=params,
        )

        return self._build_steps(
            notes=notes,
            candidates=candidates,
            chosen_indices=chosen_indices,
        )

    def _emission_cost(
        self,
        *,
        candidate: BassTabCandidateDTO,
        preferred_line: int | None,
        params: BassTabViterbiParams,
    ) -> float:
        cost: float = 0.0

        if bool(candidate.is_open):
            cost += float(params.open_string_cost)

        fret_height: int = int(candidate.fret_height)
        if fret_height == 2:
            cost += float(params.fret_height_2_cost)
        elif fret_height == 3:
            cost += float(params.fret_height_3_cost)
        elif fret_height == 4:
            cost += float(params.fret_height_4_cost)

        if preferred_line is not None and int(candidate.line) == int(preferred_line):
            cost += float(params.local_string_bonus)

        return cost

    def _transition_cost(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        note_index: int,
        prev_candidate: BassTabCandidateDTO,
        cur_candidate: BassTabCandidateDTO,
        bpm: int,
        params: BassTabViterbiParams,
    ) -> float:
        cost: float = 0.0

        prev_line: int = int(prev_candidate.line)
        cur_line: int = int(cur_candidate.line)
        prev_fret: int = int(prev_candidate.fret)
        cur_fret: int = int(cur_candidate.fret)
        dfret: int = abs(cur_fret - prev_fret)

        dt_beats: float = self._dt_beats(
            notes=notes,
            note_index=note_index,
            bpm=bpm,
        )
        speed_mult: float = self._movement_speed_multiplier(
            dt_beats=dt_beats,
            params=params,
        )

        if prev_line != cur_line:
            cost += float(params.string_change_cost) * speed_mult

        cost += float(dfret) * float(params.fret_move_cost) * speed_mult

        if prev_line == cur_line and dfret >= int(params.same_string_far_move_start):
            extra_jump: int = dfret - int(params.same_string_far_move_start) + 1
            cost += float(extra_jump) * float(params.same_string_far_move_cost) * speed_mult

        if dt_beats >= float(params.sufficient_t_beats):
            cost += float(cur_fret) * float(params.low_fret_bias_cost)

        return cost

    def _smooth_short_zigzags(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        candidates: list[list[BassTabCandidateDTO]],
        chosen_indices: list[int],
        bpm: int,
        params: BassTabViterbiParams,
    ) -> list[int]:
        """
        짧은 ABA string zigzag를 후처리로 완화한다.
        """
        out: list[int] = list(chosen_indices)
        if len(out) < 3:
            return out

        for i in range(1, len(out) - 1):
            left_cand: BassTabCandidateDTO = candidates[i - 1][out[i - 1]]
            mid_cand: BassTabCandidateDTO = candidates[i][out[i]]
            right_cand: BassTabCandidateDTO = candidates[i + 1][out[i + 1]]

            left_line: int = int(left_cand.line)
            mid_line: int = int(mid_cand.line)
            right_line: int = int(right_cand.line)

            if left_line != right_line:
                continue
            if mid_line == left_line:
                continue

            dt_left: float = self._dt_beats(notes=notes, note_index=i, bpm=bpm)
            dt_right: float = self._dt_beats(notes=notes, note_index=i + 1, bpm=bpm)
            if max(dt_left, dt_right) > float(params.string_cut_t_beats):
                continue

            best_mid_idx: int = out[i]
            best_local_cost: float = self._pair_cost(
                notes=notes,
                prev_note_index=i - 1,
                prev_candidate=left_cand,
                cur_candidate=mid_cand,
                bpm=bpm,
                params=params,
            ) + self._pair_cost(
                notes=notes,
                prev_note_index=i,
                prev_candidate=mid_cand,
                cur_candidate=right_cand,
                bpm=bpm,
                params=params,
            ) + float(params.string_zigzag_cost)

            preferred_line: int | None = self._get_local_preferred_line(
                notes=notes,
                current_index=i,
                bpm=bpm,
                local_window_bar_count=int(params.local_window_bar_count),
            )

            for alt_idx, alt_mid in enumerate(candidates[i]):
                local_cost: float = self._emission_cost(
                    candidate=alt_mid,
                    preferred_line=preferred_line,
                    params=params,
                )
                local_cost += self._pair_cost(
                    notes=notes,
                    prev_note_index=i - 1,
                    prev_candidate=left_cand,
                    cur_candidate=alt_mid,
                    bpm=bpm,
                    params=params,
                )
                local_cost += self._pair_cost(
                    notes=notes,
                    prev_note_index=i,
                    prev_candidate=alt_mid,
                    cur_candidate=right_cand,
                    bpm=bpm,
                    params=params,
                )
                if local_cost < best_local_cost:
                    best_local_cost = local_cost
                    best_mid_idx = alt_idx

            out[i] = best_mid_idx

        return out

    def _pair_cost(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        prev_note_index: int,
        prev_candidate: BassTabCandidateDTO,
        cur_candidate: BassTabCandidateDTO,
        bpm: int,
        params: BassTabViterbiParams,
    ) -> float:
        return self._transition_cost(
            notes=notes,
            note_index=prev_note_index + 1,
            prev_candidate=prev_candidate,
            cur_candidate=cur_candidate,
            bpm=bpm,
            params=params,
        )

    def _get_local_preferred_line(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        current_index: int,
        bpm: int,
        local_window_bar_count: int,
    ) -> int | None:
        if current_index < 0 or bpm <= 0:
            return None

        seconds_per_beat: float = 60.0 / float(bpm)
        bar_seconds: float = seconds_per_beat * 4.0
        if bar_seconds <= 0.0:
            return None

        cur_time: float = float(notes[current_index].start_time)
        cur_bar_index: int = int(cur_time // bar_seconds)
        if cur_bar_index == 0:
            return None

        start_bar_index: int = max(0, cur_bar_index - int(local_window_bar_count))
        start_time: float = float(start_bar_index) * bar_seconds

        values: list[int] = []
        for i in range(current_index):
            note: BasicPitchNoteEventDTO = notes[i]
            pitch: int = int(note.pitch_midi)
            if float(note.start_time) < start_time:
                continue
            if pitch in (28, 33, 38, 43):
                continue
            values.append(pitch)

        if not values:
            return None

        avg_pitch: float = float(sum(values)) / float(len(values))
        if avg_pitch < 33.0:
            return 4
        if avg_pitch < 38.0:
            return 3
        if avg_pitch < 43.0:
            return 2
        return 1

    def _movement_speed_multiplier(
        self,
        *,
        dt_beats: float,
        params: BassTabViterbiParams,
    ) -> float:
        cut_t: float = float(params.string_cut_t_beats)
        if cut_t <= 0.0:
            return 1.0
        if dt_beats >= cut_t:
            return 1.0
        if dt_beats <= 0.0:
            return 2.0
        ratio: float = (cut_t - dt_beats) / cut_t
        return 1.0 + min(1.0, ratio)

    def _dt_beats(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        note_index: int,
        bpm: int,
    ) -> float:
        if note_index <= 0:
            return 0.0
        seconds_per_beat: float = 60.0 / float(bpm)
        if seconds_per_beat <= 0.0:
            return 0.0
        dt_seconds: float = (
            float(notes[note_index].start_time) - float(notes[note_index - 1].start_time)
        )
        if dt_seconds <= 0.0:
            return 0.0
        return dt_seconds / seconds_per_beat

    def _traceback(
        self,
        *,
        back_ptr: list[list[int]],
        last_best_idx: int,
    ) -> list[int]:
        n_notes: int = len(back_ptr)
        chosen_indices: list[int] = [0] * n_notes
        chosen_indices[-1] = last_best_idx
        for i in range(n_notes - 1, 0, -1):
            chosen_indices[i - 1] = back_ptr[i][chosen_indices[i]]
        return chosen_indices

    def _build_steps(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        candidates: list[list[BassTabCandidateDTO]],
        chosen_indices: list[int],
    ) -> list[BassTabViterbiStepDTO]:
        out: list[BassTabViterbiStepDTO] = []
        for i in range(len(notes)):
            chosen: BassTabCandidateDTO = candidates[i][chosen_indices[i]]
            note: BasicPitchNoteEventDTO = notes[i]
            out.append(
                BassTabViterbiStepDTO(
                    note_index=i,
                    pitch_midi=int(note.pitch_midi),
                    start_time=float(note.start_time),
                    end_time=float(note.end_time),
                    line=int(chosen.line),
                    fret=int(chosen.fret),
                )
            )
        return out

    def _argmin(self, *, values: list[float]) -> int:
        best_idx: int = 0
        best_value: float = values[0]
        for i in range(1, len(values)):
            if values[i] < best_value:
                best_value = values[i]
                best_idx = i
        return best_idx