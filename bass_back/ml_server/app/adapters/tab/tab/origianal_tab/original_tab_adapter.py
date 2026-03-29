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
    OriginalTabGeneratePort,
)
from app.application.ports.tab.tab.original_tab.viterbi_port import (
    BassTabViterbiParams,
    BassTabViterbiPort,
    BassTabViterbiStepDTO,
)

from app.adapters.ml_supabase_adapter import SupabaseAudioHandler

def _log_step(message: str) -> None:
    print(f"[original_tab] {message}")


@dataclass(frozen=True)
class OriginalTabGenerateAdapter(OriginalTabGeneratePort):
    candidate_builder: BassTabCandidateBuilderPort
    viterbi: BassTabViterbiPort
    handler: SupabaseAudioHandler  
    output_filename: str = "original_tab.json"

    beats_per_bar: int = 4
    candidate_params: BassTabCandidateBuildParams = field(
        default_factory=BassTabCandidateBuildParams
    )
    viterbi_params: BassTabViterbiParams = field(
        default_factory=BassTabViterbiParams
    )

    async def tab_generate(
        self,
        *,
        original_json: list[BasicPitchNoteEventDTO],
        bpm: int,
        output_dir: str,  # Path에서 str(URL)로 변경
        asset_id: str,
    ) -> bool:  # 반환 타입을 업로드 성공 여부(bool)로 변경
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

            # 2. 후보군 빌드 및 Viterbi 디코딩 (기존 로직 유지)
            raw_candidates: list[list[BassTabCandidateDTO]] = self.candidate_builder.build_candidates(
                notes=sorted_notes,
                params=self.candidate_params,
            )

            valid_notes: list[BasicPitchNoteEventDTO] = []
            valid_candidates: list[list[BassTabCandidateDTO]] = []
            
            for i, one_candidates in enumerate(raw_candidates):
                if not one_candidates:
                    continue
                valid_notes.append(sorted_notes[i])
                valid_candidates.append(one_candidates)

            if valid_notes:
                steps: list[BassTabViterbiStepDTO] = self.viterbi.decode(
                    notes=valid_notes,
                    candidates=valid_candidates,
                    bpm=int(bpm),
                    params=self.viterbi_params,
                )

                # 3. 마디 그룹화
                bars = self._group_steps_by_bar(
                    steps=steps,
                    bpm=int(bpm),
                    beats_per_bar=int(self.beats_per_bar),
                )

        # 4. JSON 페이로드 생성
        payload = self._create_json_payload(bars=bars)

        # 5. 업로드 목적지 URL 구성 및 업로드
        target_upload_url = f"{output_dir.rstrip('/')}/assets/{asset_id}/tab/{self.output_filename}"
        
        _log_step(f"📤 결과 업로드 중... ({target_upload_url})")

        success = await self.handler.upload_json_to_supabase(
            payload=payload,
            target_supabase_url=target_upload_url
        )
        
        return success

    def _create_json_payload(self, bars: list[BassTabBarDTO]) -> list[dict]:
        """DTO 데이터를 직렬화 가능한 딕셔너리 리스트로 변환합니다."""
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

    def _group_steps_by_bar(
        self,
        *,
        steps: list[BassTabViterbiStepDTO],
        bpm: int,
        beats_per_bar: int,
    ) -> list[BassTabBarDTO]:
        if not steps:
            return []
        
        seconds_per_beat: float = 60.0 / float(bpm)
        bar_seconds: float = seconds_per_beat * float(beats_per_bar)

        bars_map: dict[int, list[BassTabBarNoteDTO]] = {}

        for step in steps:
            time: float = float(step.start_time)
            bar_index: int = int(time // bar_seconds)
            bar_start_time: float = float(bar_index) * bar_seconds
            offset: float = (time - bar_start_time) / seconds_per_beat

            note_dto: BassTabBarNoteDTO = BassTabBarNoteDTO(
                time=time,
                offset=offset,
                line=int(step.line),
                fret=int(step.fret),
            )

            if bar_index not in bars_map:
                bars_map[bar_index] = []
            bars_map[bar_index].append(note_dto)

        out: list[BassTabBarDTO] = []
        for bar_index in sorted(bars_map.keys()):
            bar_start_time: float = float(bar_index) * bar_seconds
            bar_end_time: float = bar_start_time + bar_seconds
            notes_in_bar: list[BassTabBarNoteDTO] = sorted(
                bars_map[bar_index],
                key=lambda x: (float(x.time), float(x.offset), int(x.line), int(x.fret)),
            )

            out.append(
                BassTabBarDTO(
                    bar_index=bar_index,
                    start_time=bar_start_time,
                    end_time=bar_end_time,
                    notes=notes_in_bar,
                )
            )

        return out