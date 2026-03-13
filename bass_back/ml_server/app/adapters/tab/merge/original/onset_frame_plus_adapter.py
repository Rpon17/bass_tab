from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.merge.original.onset_frame_plus_port import (
    OnsetFrameFuseParams,
    OnsetFrameFusePort,
)


@dataclass(frozen=True)
class OnsetFrameFuseAdapter(OnsetFrameFusePort):
    """
    결합 규칙 (sustain 미사용 버전)

    1) onset을 기본 뼈대로 사용 (onset 우선)
    2) frame은 "누락(missing) 보강"만 사용 (onset과 겹치면 버림)
    3) 마지막에 BPM 기반 grid quantization (옵션)
    """

    output_filename: str = "real_original.json"

    def normalize(
        self,
        *,
        bpm: float,
        onset_notes: list[BasicPitchNoteEventDTO],
        frame_notes: list[BasicPitchNoteEventDTO],
        params: OnsetFrameFuseParams,
    ) -> list[BasicPitchNoteEventDTO]:
        onset_sorted: list[BasicPitchNoteEventDTO] = sorted(
            onset_notes,
            key=lambda n: (float(n.start_time), float(n.end_time), int(n.pitch_midi)),
        )
        frame_sorted: list[BasicPitchNoteEventDTO] = sorted(
            frame_notes,
            key=lambda n: (float(n.start_time), float(n.end_time), int(n.pitch_midi)),
        )

        if not onset_sorted:
            # "첫 음은 onset 이후" 정책상 onset이 없으면 결과도 없음
            return []

        # first_onset 이전 frame 제거
        first_onset_start: float = float(onset_sorted[0].start_time)
        frame_filtered: list[BasicPitchNoteEventDTO] = [
            f for f in frame_sorted if float(f.start_time) >= first_onset_start
        ]

        # onset skeleton 만들기 (유효한 노트만)
        onset_skeleton: list[BasicPitchNoteEventDTO] = [
            BasicPitchNoteEventDTO(
                start_time=float(o.start_time),
                end_time=float(o.end_time),
                pitch_midi=int(o.pitch_midi),
                confidence=None if o.confidence is None else float(o.confidence),
            )
            for o in onset_sorted
            if float(o.end_time) > float(o.start_time)
        ]
        if not onset_skeleton:
            return []

        # sustain 확장 안 함
        skeleton: list[BasicPitchNoteEventDTO] = list(onset_skeleton)

        if not frame_filtered:
            return self._finalize(bpm=bpm, notes=skeleton, params=params)

        inserts: list[BasicPitchNoteEventDTO] = []
        sec_per_step: float = self._sec_per_step(bpm=bpm, params=params)
        min_len: float = float(params.missing_min_steps) * sec_per_step

        for f in frame_filtered:
            frame_start: float = float(f.start_time)
            frame_end: float = float(f.end_time)
            frame_pitch: int = int(f.pitch_midi)

            if frame_end <= frame_start:
                continue

            # onset과 겹치면 삽입 금지
            if self._frame_overlaps_any_onset(
                f0=frame_start,
                f1=frame_end,
                onsets=skeleton,
                params=params,
            ):
                continue

            # onset "사이" 구간에만 삽입 허용 (마지막 이후는 기본 불허)
            if not self._is_frame_between_onsets(
                f0=frame_start,
                f1=frame_end,
                onsets=skeleton,
                bpm=bpm,
                params=params,
            ):
                continue

            # 최소 길이 조건
            if (frame_end - frame_start) + 1e-9 < min_len:
                continue

            inserts.append(
                BasicPitchNoteEventDTO(
                    start_time=frame_start,
                    end_time=frame_end,
                    pitch_midi=frame_pitch,
                    confidence=f.confidence,
                )
            )

        combined: list[BasicPitchNoteEventDTO] = sorted(
            skeleton + inserts,
            key=lambda n: (float(n.start_time), float(n.end_time), int(n.pitch_midi)),
        )

        return self._finalize(bpm=bpm, notes=combined, params=params)

    def normalize_file(
        self,
        *,
        bpm: float,
        onset_notes: list[BasicPitchNoteEventDTO],
        frame_notes: list[BasicPitchNoteEventDTO],
        output_dir: str,
        params: OnsetFrameFuseParams,
        overwrite=True
    ) -> None:
        out: list[BasicPitchNoteEventDTO] = self.normalize(
            bpm=bpm,
            onset_notes=onset_notes,
            frame_notes=frame_notes,
            params=params,
        )

        out_dir: Path = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path: Path = out_dir / self.output_filename

        payload: list[dict[str, Any]] = [
            {
                "start_time": float(n.start_time),
                "end_time": float(n.end_time),
                "pitch_midi": int(n.pitch_midi),
                "confidence": None if n.confidence is None else float(n.confidence),
            }
            for n in out
        ]
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # -------------------------
    # helpers
    # -------------------------

    def _sec_per_step(self, *, bpm: float, params: OnsetFrameFuseParams) -> float:
        bpm_f: float = float(bpm)
        if bpm_f <= 0.0:
            raise ValueError("bpm must be > 0")

        steps_per_beat: int = int(params.steps_per_beat)
        if steps_per_beat <= 0:
            raise ValueError("params.steps_per_beat must be > 0")

        sec_per_beat: float = 60.0 / bpm_f
        return sec_per_beat / float(steps_per_beat)

    @staticmethod
    def _overlap_len(*, a0: float, a1: float, b0: float, b1: float) -> float:
        lo: float = max(float(a0), float(b0))
        hi: float = min(float(a1), float(b1))
        return 0.0 if hi <= lo else float(hi - lo)

    def _frame_overlaps_any_onset(
        self,
        *,
        f0: float,
        f1: float,
        onsets: list[BasicPitchNoteEventDTO],
        params: OnsetFrameFuseParams,
    ) -> bool:
        """
        frame [f0,f1) 이 onset 구간과 min_overlap_seconds 이상 겹치면 True.
        sustain을 안 쓰므로 pitch 비교 없이 시간 겹침만 본다.
        """
        min_ov_sec: float = float(getattr(params, "min_overlap_seconds", 0.0))
        if min_ov_sec < 0.0:
            min_ov_sec = 0.0

        for o in onsets:
            o0: float = float(o.start_time)
            o1: float = float(o.end_time)
            ov: float = self._overlap_len(a0=f0, a1=f1, b0=o0, b1=o1)
            if ov + 1e-12 >= min_ov_sec and ov > 0.0:
                return True

        return False

    def _is_frame_between_onsets(
        self,
        *,
        f0: float,
        f1: float,
        onsets: list[BasicPitchNoteEventDTO],
        bpm: float,
        params: OnsetFrameFuseParams,
    ) -> bool:
        """
        frame이 onset 사이의 빈 구간에 '완전히' 들어가면 True.

        - 기본: 마지막 onset 이후는 False (끝에 노이즈 붙는 걸 방지)
        - 옵션: params.allow_after_last_onset=True 이면, after_last_tail_steps 이내만 허용
        """
        if not onsets:
            return False

        # (옵션) 마지막 onset 이후 허용
        allow_after_last: bool = bool(getattr(params, "allow_after_last_onset", False))
        after_tail_steps: int = int(getattr(params, "after_last_tail_steps", 0))
        last_end: float = float(onsets[-1].end_time)
        if f0 >= last_end:
            if not allow_after_last:
                return False
            if after_tail_steps <= 0:
                return False
            sec_per_step: float = self._sec_per_step(bpm=bpm, params=params)
            tail_allow: float = float(after_tail_steps) * sec_per_step
            return (f0 - last_end) <= tail_allow

        # onset 사이 빈 구간
        for i in range(1, len(onsets)):
            prev_end: float = float(onsets[i - 1].end_time)
            next_start: float = float(onsets[i].start_time)
            if f0 >= prev_end and f1 <= next_start:
                return True

        return False

    def _finalize(
        self,
        *,
        bpm: float,
        notes: list[BasicPitchNoteEventDTO],
        params: OnsetFrameFuseParams,
    ) -> list[BasicPitchNoteEventDTO]:
        if not notes:
            return []

        # quantize 끄면 정렬만
        if not bool(params.quantize):
            return sorted(
                [
                    BasicPitchNoteEventDTO(
                        start_time=float(n.start_time),
                        end_time=float(n.end_time),
                        pitch_midi=int(n.pitch_midi),
                        confidence=n.confidence,
                    )
                    for n in notes
                    if float(n.end_time) > float(n.start_time)
                ],
                key=lambda n: (float(n.start_time), float(n.end_time), int(n.pitch_midi)),
            )

        sec_per_step: float = self._sec_per_step(bpm=bpm, params=params)

        out: list[BasicPitchNoteEventDTO] = []
        for n in notes:
            st: float = float(n.start_time)
            et: float = float(n.end_time)
            if et <= st:
                continue

            qs: float = round(st / sec_per_step) * sec_per_step
            qe: float = round(et / sec_per_step) * sec_per_step

            # 최소 1 step 길이 보장
            if qe <= qs:
                qe = qs + sec_per_step

            out.append(
                BasicPitchNoteEventDTO(
                    start_time=float(qs),
                    end_time=float(qe),
                    pitch_midi=int(n.pitch_midi),
                    confidence=n.confidence,
                )
            )

        return sorted(out, key=lambda n: (float(n.start_time), float(n.end_time), int(n.pitch_midi)))