from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.tab.original_tab.candidate_port import (
    BassTabCandidateBuildParams,
    BassTabCandidateBuilderPort,
    BassTabCandidateDTO,
)
from app.application.ports.tab.tab.original_tab.original_tab_port import (
    BassTabBarDTO,
    BassTabBarNoteDTO,
)

from app.adapters.ml_supabase_adapter import SupabaseAudioHandler

def _log_step(message: str) -> None:
    print(f"[root_tab] {message}")


@dataclass(frozen=True)
class RootTabGenerateAdapter:
    candidate_builder: BassTabCandidateBuilderPort
    handler: SupabaseAudioHandler
    output_filename: str = "root_tab.json"

    beats_per_bar: int = 4
    candidate_params: BassTabCandidateBuildParams = field(
        default_factory=BassTabCandidateBuildParams
    )

    async def tab_generate(
        self,
        *,
        original_json: list[BasicPitchNoteEventDTO],
        bpm: int,
        output_dir: str,  # 스토리지 베이스 URL
        asset_id: str,
    ) -> bool:
        """
        노트 데이터를 분석하여 베이스 루트 타브를 생성하고 Supabase에 직접 업로드합니다.
        로컬 파일을 생성하지 않습니다.
        """
        if bpm <= 0:
            raise ValueError("bpm must be > 0")
        if self.beats_per_bar <= 0:
            raise ValueError("beats_per_bar must be > 0")

        # 1. 노트 필터링 및 정렬
        filtered_notes: list[BasicPitchNoteEventDTO] = self._filter_notes(notes=original_json)

        bars: list[BassTabBarDTO] = []
        if filtered_notes:
            sorted_notes: list[BasicPitchNoteEventDTO] = sorted(
                filtered_notes,
                key=lambda x: (float(x.start_time), float(x.end_time), int(x.pitch_midi)),
            )

            # 2. 마디별 루트 피치 추출 및 타브 생성
            bars = self._build_root_bars(
                notes=sorted_notes,
                bpm=bpm,
                beats_per_bar=self.beats_per_bar,
            )

        # 3. JSON 페이로드 생성
        payload = self._create_json_payload(bars=bars)

        # 4. 업로드 경로 및 URL 구성
        target_upload_url = f"{output_dir.rstrip('/')}/asset/{asset_id}/tab/{self.output_filename}"

        _log_step(f"📤 결과 업로드 중... ({target_upload_url})")

        # 5. 핸들러를 통한 메모리 직접 업로드
        success = await self.handler.upload_json_to_supabase(
            payload=payload,
            target_supabase_url=target_upload_url
        )
        
        return success

    def _create_json_payload(self, bars: list[BassTabBarDTO]) -> list[dict]:
        """DTO 데이터를 JSON 직렬화가 가능한 딕셔너리 리스트로 변환합니다."""
        payload: list[dict] = []
        for bar in bars:
            payload.append({
                "bar_index": int(bar.bar_index),
                "start_time": float(bar.start_time),
                "end_time": float(bar.end_time),
                "notes": [
                    {
                        "time": float(note.time),
                        "offset": float(note.offset),
                        "line": int(note.line),
                        "fret": int(note.fret),
                    }
                    for note in bar.notes
                ],
            })
        return payload

    def _filter_notes(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
    ) -> list[BasicPitchNoteEventDTO]:
        out: list[BasicPitchNoteEventDTO] = []
        for note in notes:
            start_time: float = float(note.start_time)
            end_time: float = float(note.end_time)
            if end_time <= start_time:
                continue
            out.append(note)
        return out

    def _build_root_bars(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        bpm: int,
        beats_per_bar: int,
    ) -> list[BassTabBarDTO]:
        seconds_per_beat: float = 60.0 / float(bpm)
        bar_seconds: float = seconds_per_beat * float(beats_per_bar)

        if not notes:
            return []

        first_time: float = float(notes[0].start_time)
        last_time: float = float(notes[-1].end_time)

        start_bar_index: int = int(first_time // bar_seconds)
        last_bar_index: int = int((last_time - 1e-9) // bar_seconds)

        out: list[BassTabBarDTO] = []

        for bar_index in range(start_bar_index, last_bar_index + 1):
            bar_start_time: float = float(bar_index) * bar_seconds
            bar_end_time: float = bar_start_time + bar_seconds

            bar_pitch: int | None = self._pick_bar_root_pitch(
                notes=notes,
                bar_start_time=bar_start_time,
                bar_end_time=bar_end_time,
            )
            if bar_pitch is None:
                continue

            root_candidate: BassTabCandidateDTO | None = self._pick_root_candidate(
                pitch_midi=bar_pitch,
            )
            if root_candidate is None:
                print(
                    f"[ROOT TAB SKIP] bar_index={bar_index} "
                    f"pitch={bar_pitch} has no playable candidate"
                )
                continue

            bar_notes: list[BassTabBarNoteDTO] = []
            for beat_idx in range(beats_per_bar):
                offset: float = float(beat_idx)
                time: float = bar_start_time + (offset * seconds_per_beat)

                bar_notes.append(
                    BassTabBarNoteDTO(
                        time=time,
                        offset=offset,
                        line=int(root_candidate.line),
                        fret=int(root_candidate.fret),
                    )
                )

            out.append(
                BassTabBarDTO(
                    bar_index=bar_index,
                    start_time=bar_start_time,
                    end_time=bar_end_time,
                    notes=bar_notes,
                )
            )

        return out

    def _pick_bar_root_pitch(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        bar_start_time: float,
        bar_end_time: float,
    ) -> int | None:
        pitch_scores: dict[int, float] = {}

        for note in notes:
            note_start: float = float(note.start_time)
            note_end: float = float(note.end_time)

            overlap: float = self._overlap_len(
                a0=note_start,
                a1=note_end,
                b0=bar_start_time,
                b1=bar_end_time,
            )
            if overlap <= 0.0:
                continue

            pitch_midi: int = int(note.pitch_midi)
            pitch_scores[pitch_midi] = pitch_scores.get(pitch_midi, 0.0) + overlap

        if not pitch_scores:
            return None

        best_pitch: int | None = None
        best_score: float = -1.0

        for pitch_midi, score in pitch_scores.items():
            if score > best_score:
                best_score = score
                best_pitch = pitch_midi
                continue

            if score == best_score and best_pitch is not None:
                if int(pitch_midi) < int(best_pitch):
                    best_pitch = pitch_midi

        return best_pitch

    def _pick_root_candidate(
        self,
        *,
        pitch_midi: int,
    ) -> BassTabCandidateDTO | None:
        dummy_note: BasicPitchNoteEventDTO = BasicPitchNoteEventDTO(
            start_time=0.0,
            end_time=1.0,
            pitch_midi=int(pitch_midi),
            confidence=None,
        )

        built: list[list[BassTabCandidateDTO]] = self.candidate_builder.build_candidates(
            notes=[dummy_note],
            params=self.candidate_params,
        )
        if not built or not built[0]:
            return None

        candidates: list[BassTabCandidateDTO] = list(built[0])

        # 낮은 fret 우선, 동률이면 낮은 줄(4번줄 쪽) 우선
        candidates.sort(
            key=lambda c: (
                int(c.fret),
                -int(c.line),
            )
        )
        return candidates[0]

    def _overlap_len(
        self,
        *,
        a0: float,
        a1: float,
        b0: float,
        b1: float,
    ) -> float:
        lo: float = a0 if a0 >= b0 else b0
        hi: float = a1 if a1 <= b1 else b1
        return 0.0 if hi <= lo else float(hi - lo)