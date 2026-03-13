from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.dtos.main_ml_dto import MLProcessRequestDTO

from app.application.usecases.final_usecase import RunMLProcessUseCase
from app.application.ports.basic_pitch.basic_pitch_port import (
    BasicPitchFramePitchDTO,
    BasicPitchNoteEventDTO,
)
from app.application.ports.tab.tab.original_tab.candidate_port import (
    BassTabCandidateDTO,
)
from app.application.ports.tab.tab.original_tab.viterbi_port import (
    BassTabViterbiStepDTO,
)
from app.domain.models_domain import MLJob


from app.adapters.bpm.bpm_estimate_adapter import LibrosaBpmEstimator
from app.adapters.demucs.demucs_adapter import DemucsAdapter
from app.adapters.basic_pitch.basic_pitch_adapter import BasicPitchAdapter


# ---------------------------
# Fake JobStore
# ---------------------------

@dataclass
class FakeJobStore:
    job: MLJob

    async def get(self, job_id: str) -> MLJob | None:
        if job_id != self.job.job_id:
            return None
        return self.job

    async def save(self, job: MLJob) -> None:
        self.job = job


# ---------------------------
# Fake Later-stage Ports
# ---------------------------

@dataclass
class FakeFrameOctavePort:
    def normalize(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: Any,
    ) -> list[BasicPitchFramePitchDTO]:
        return frames


@dataclass
class FakeFrameNoteNormalizePort:
    def normalize(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: Any,
    ) -> list[BasicPitchNoteEventDTO]:
        out: list[BasicPitchNoteEventDTO] = []

        for frame in frames:
            out.append(
                BasicPitchNoteEventDTO(
                    start_time=float(frame.t),
                    end_time=float(frame.t) + 0.25,
                    pitch_midi=int(frame.pitch_midi),
                    confidence=None if frame.confidence is None else float(frame.confidence),
                )
            )

        return out


@dataclass
class FakeOnsetOctavePort:
    def normalize(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: Any,
    ) -> list[BasicPitchNoteEventDTO]:
        return notes


@dataclass
class FakeOnsetNormalizePort:
    def normalize(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: Any,
    ) -> list[BasicPitchNoteEventDTO]:
        return notes


@dataclass
class FakeOnsetFrameFusePort:
    def normalize(
        self,
        *,
        bpm: float,
        onset_notes: list[BasicPitchNoteEventDTO],
        frame_notes: list[BasicPitchNoteEventDTO],
        params: Any,
    ) -> list[BasicPitchNoteEventDTO]:
        return onset_notes if onset_notes else frame_notes


@dataclass
class FakeRootTabBuildPort:
    def build(
        self,
        *,
        bpm: float,
        original_notes: list[BasicPitchNoteEventDTO],
        params: Any,
    ) -> list[BasicPitchNoteEventDTO]:
        return original_notes


@dataclass
class FakeBassTabCandidateBuilderPort:
    def build_candidates(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: Any,
    ) -> list[list[BassTabCandidateDTO]]:
        out: list[list[BassTabCandidateDTO]] = []

        for note in notes:
            fret: int = max(0, int(note.pitch_midi) - 28)
            out.append(
                [
                    BassTabCandidateDTO(
                        line=4,
                        fret=fret,
                        is_open=(fret == 0),
                        fret_height=fret,
                    )
                ]
            )

        return out


@dataclass
class FakeBassTabViterbiPort:
    def decode(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        candidates: list[list[BassTabCandidateDTO]],
        bpm: int,
        params: Any,
    ) -> list[BassTabViterbiStepDTO]:
        out: list[BassTabViterbiStepDTO] = []

        for i, note in enumerate(notes):
            cand: BassTabCandidateDTO = candidates[i][0]
            out.append(
                BassTabViterbiStepDTO(
                    note_index=i,
                    pitch_midi=int(note.pitch_midi),
                    start_time=float(note.start_time),
                    end_time=float(note.end_time),
                    line=int(cand.line),
                    fret=int(cand.fret),
                )
            )

        return out


@dataclass
class FakeOriginalTabGeneratePort:
    def tab_generate(
        self,
        *,
        original_json: list[BassTabViterbiStepDTO],
        bpm: int,
        output_dir: Path,
        asset_id: str,
    ) -> Path:
        tab_dir: Path = output_dir / "tab"
        tab_dir.mkdir(parents=True, exist_ok=True)

        payload: list[dict[str, object]] = []
        for step in original_json:
            payload.append(
                {
                    "note_index": int(step.note_index),
                    "pitch_midi": int(step.pitch_midi),
                    "start_time": float(step.start_time),
                    "end_time": float(step.end_time),
                    "line": int(step.line),
                    "fret": int(step.fret),
                }
            )

        out_path: Path = tab_dir / "original_tab.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out_path


@dataclass
class FakeRootTabGenerateAdapter:
    def tab_generate(
        self,
        *,
        original_json: list[BasicPitchNoteEventDTO],
        bpm: int,
        output_dir: Path,
        asset_id: str,
    ) -> Path:
        tab_dir: Path = output_dir / "tab"
        tab_dir.mkdir(parents=True, exist_ok=True)

        payload: list[dict[str, object]] = []
        for note in original_json:
            payload.append(
                {
                    "start_time": float(note.start_time),
                    "end_time": float(note.end_time),
                    "pitch_midi": int(note.pitch_midi),
                    "confidence": None if note.confidence is None else float(note.confidence),
                }
            )

        out_path: Path = tab_dir / "root_tab.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out_path


# ---------------------------
# Main
# ---------------------------

async def main() -> None:

    input_wav_path: Path = Path(r"C:\bass_project\storage\songs\c422012dd22046ab95f91e537d59be1a\results\90b97c8940ef4dc1af030140ebb1b691\audio\original.mp3")

    if not input_wav_path.exists():
        raise FileNotFoundError(f"real test wav not found: {input_wav_path}")

    test_root: Path = Path(r"C:\bass_project\storage\usecase_real_test")
    asset_root: Path = test_root / "asset_root"

    if test_root.exists():
        shutil.rmtree(test_root)

    asset_root.mkdir(parents=True, exist_ok=True)

    job: MLJob = MLJob(
        job_id="job_real_test_001",
        result_id="result_real_test_001",
        song_id="song_real_test_001",
        asset_id="asset_real_test_001",
        input_wav_path=str(input_wav_path),
        output_dir=str(asset_root),
    )

    real_demucs_port: DemucsAdapter = DemucsAdapter()
    real_basic_pitch_port: BasicPitchAdapter = BasicPitchAdapter()
    real_bpm_port: LibrosaBpmEstimator = LibrosaBpmEstimator()

    usecase: RunMLProcessUseCase = RunMLProcessUseCase(
        job_store=FakeJobStore(job=job),
        bpm_port=real_bpm_port,
        demucs_port=real_demucs_port,
        basic_pitch_port=real_basic_pitch_port,
        frame_octave_port=FakeFrameOctavePort(),
        frame_note_normalize_port=FakeFrameNoteNormalizePort(),
        onset_octave_port=FakeOnsetOctavePort(),
        onset_normalize_port=FakeOnsetNormalizePort(),
        onset_frame_fuse_port=FakeOnsetFrameFusePort(),
        root_tab_build_port=FakeRootTabBuildPort(),
        bass_tab_candidate_builder_port=FakeBassTabCandidateBuilderPort(),
        bass_tab_viterbi_port=FakeBassTabViterbiPort(),
        original_tab_generate_port=FakeOriginalTabGeneratePort(),
        root_tab_generate_adapter=FakeRootTabGenerateAdapter(),
    )

    request: MLProcessRequestDTO = MLProcessRequestDTO(
        job_id="job_real_test_001",
        song_id="song_real_test_001",
        result_id="result_real_test_001",
        asset_id="asset_real_test_001",
        input_wav_path=str(input_wav_path),
        result_path=str(asset_root),
        norm_title="real_test_title",
        norm_artist="real_test_artist",
    )

    response = await usecase.execute(request=request)

    print("=== RESPONSE ===")
    print(response)
    
    demucs_audio_dir: Path = asset_root / "asset" / "asset_real_test_001" / "audio"
    bass_only_path: Path = demucs_audio_dir / "bass_only.wav"
    original_tab_path: Path = asset_root / "tab" / "original_tab.json"
    root_tab_path: Path = asset_root / "tab" / "root_tab.json"

    print("=== FILE CHECK ===")
    print(f"bass_only exists: {bass_only_path.exists()}")
    print(f"original_tab exists: {original_tab_path.exists()}")
    print(f"root_tab exists: {root_tab_path.exists()}")

    if response.status != "done":
        raise AssertionError(f"expected done, got {response.status}, error={response.error}")

    if not bass_only_path.exists():
        raise AssertionError("bass_only.wav was not created")

    if not original_tab_path.exists():
        raise AssertionError("original_tab.json was not created")

    if not root_tab_path.exists():
        raise AssertionError("root_tab.json was not created")

    print("=== REAL TEST PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())