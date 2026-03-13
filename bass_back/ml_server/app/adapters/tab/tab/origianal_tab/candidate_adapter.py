from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.tab.original_tab.candidate_port import (
    BassTabCandidateBuildParams,
    BassTabCandidateBuilderPort,
    BassTabCandidateDTO,
)


@dataclass(frozen=True)
class BassTabCandidateBuilderAdapter(BassTabCandidateBuilderPort):
    """
    Candidate builder for bass tablature.

    정책:
    - 한 note에 대해 물리적으로 가능한 모든 string/fret 후보를 남긴다.
    - 불가능한 후보만 제거한다.
    - 직접 후보가 없으면 -12 octave fallback을 반복 시도한다.
    - 그래도 없으면 빈 후보로 남긴다. (상위 레이어에서 후처리 가능)
    """

    def build_candidates(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: BassTabCandidateBuildParams,
    ) -> list[list[BassTabCandidateDTO]]:
        out: list[list[BassTabCandidateDTO]] = []

        for note_idx, note in enumerate(notes):
            original_pitch: int = int(note.pitch_midi)

            one_candidates: list[BassTabCandidateDTO] = self._build_one_candidates(
                note_pitch=original_pitch,
                params=params,
            )

            if one_candidates:
                out.append(one_candidates)
                continue

            fallback_pitch: int = original_pitch
            fallback_used: bool = False

            while fallback_pitch - 12 >= 0:
                fallback_pitch -= 12
                one_candidates = self._build_one_candidates(
                    note_pitch=fallback_pitch,
                    params=params,
                )
                if one_candidates:
                    fallback_used = True
                    print(
                        f"[OCTAVE FALLBACK] idx={note_idx} "
                        f"pitch={original_pitch} -> {fallback_pitch} "
                        f"start={float(note.start_time)} "
                        f"end={float(note.end_time)}"
                    )
                    break

            if not one_candidates:
                print(
                    f"[NO CANDIDATE] idx={note_idx} "
                    f"pitch={original_pitch} "
                    f"start={float(note.start_time)} "
                    f"end={float(note.end_time)}"
                )
            elif fallback_used:
                one_candidates = self._sort_candidates(candidates=one_candidates)

            out.append(one_candidates)

        return out

    def _build_one_candidates(
        self,
        *,
        note_pitch: int,
        params: BassTabCandidateBuildParams,
    ) -> list[BassTabCandidateDTO]:
        one_candidates: list[BassTabCandidateDTO] = []
        seen: set[tuple[int, int]] = set()

        for tuning in params.tuning:
            fret: int = int(note_pitch - int(tuning.open_pitch))
            if fret < int(params.min_fret):
                continue
            if fret > int(params.max_fret):
                continue

            key: tuple[int, int] = (int(tuning.line), fret)
            if key in seen:
                continue
            seen.add(key)

            one_candidates.append(
                BassTabCandidateDTO(
                    line=int(tuning.line),
                    fret=fret,
                    is_open=(fret == 0),
                    fret_height=self._get_fret_height(fret=fret),
                )
            )

        return self._sort_candidates(candidates=one_candidates)

    def _sort_candidates(
        self,
        *,
        candidates: list[BassTabCandidateDTO],
    ) -> list[BassTabCandidateDTO]:
        candidates.sort(
            key=lambda c: (
                int(c.fret),          # 낮은 프렛 우선
                0 if bool(c.is_open) else 1,
                -int(c.line),         # tie면 낮은 줄(E쪽) 먼저
            )
        )
        return candidates

    def _get_fret_height(self, *, fret: int) -> int:
        if fret <= 5:
            return 1
        if fret <= 11:
            return 2
        if fret <= 16:
            return 3
        return 4