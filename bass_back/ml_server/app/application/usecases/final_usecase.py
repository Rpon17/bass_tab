from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from shared.dtos.main_ml_dto import (
    MLProcessRequestDTO,
    MLProcessResponseDTO,
)

from app.application.ports.jobs.job_store_port import JobStore
from app.application.ports.bpm.bpm_port import BpmEstimatePort
from app.application.ports.demucs.demucs_port import (
    DemucsDspParams,
    DemucsPort,
    DemucsSplitSetting,
)
from app.application.ports.basic_pitch.basic_pitch_port import (
    BasicPitchFramePitchDTO,
    BasicPitchNoteEventDTO,
    BasicPitchParams,
    BasicPitchPort,
)
from app.application.ports.tab.frame.frame_octave_port import (
    FramePitchOctaveNormalizeParams,
    FramePitchOctaveNormalizePort,
)
from app.application.ports.tab.frame.frame_note_normalization_port import (
    FramePitchNormalizeParams,
    FramePitchNormalizePort,
)
from app.application.ports.tab.onset.onset_octave_port import (
    OnsetPitchOctaveNormalizeParams,
    OnsetPitchOctaveNormalizePort,
)
from app.application.ports.tab.onset.onset_json_noramization_port import (
    OnsetNormalizeParams,
    OnsetNormalizePort,
)
from app.application.ports.tab.merge.original.onset_frame_plus_port import (
    OnsetFrameFuseParams,
    OnsetFrameFusePort,
)
from app.application.ports.tab.merge.root.root_note_port import (
    RootTabBuildPort,
)
from app.application.ports.tab.tab.original_tab.candidate_port import (
    BassTabCandidateBuildParams,
    BassTabCandidateBuilderPort,
    BassTabCandidateDTO,
)
from app.application.ports.tab.tab.original_tab.viterbi_port import (
    BassTabViterbiParams,
    BassTabViterbiPort,
    BassTabViterbiStepDTO,
)
from app.application.ports.tab.tab.original_tab.original_tab_port import (
    OriginalTabGeneratePort,
)
from app.adapters.tab.tab.root_tab.root_tab_adapter import RootTabGenerateAdapter

from app.domain.models_domain import MLJob


@dataclass(frozen=True)
class RunMLProcessUseCase:
    job_store: JobStore
    bpm_port: BpmEstimatePort
    demucs_port: DemucsPort
    basic_pitch_port: BasicPitchPort
    frame_octave_port: FramePitchOctaveNormalizePort
    frame_note_normalize_port: FramePitchNormalizePort
    onset_octave_port: OnsetPitchOctaveNormalizePort
    onset_normalize_port: OnsetNormalizePort
    onset_frame_fuse_port: OnsetFrameFusePort
    root_tab_build_port: RootTabBuildPort
    bass_tab_candidate_builder_port: BassTabCandidateBuilderPort
    bass_tab_viterbi_port: BassTabViterbiPort
    original_tab_generate_port: OriginalTabGeneratePort
    root_tab_generate_adapter: RootTabGenerateAdapter

    async def execute(
        self,
        *,
        request: MLProcessRequestDTO,
    ) -> MLProcessResponseDTO:
        stage: str = "init"

        print("[USECASE] 시작")

        job: MLJob = await self._get_job(request.job_id)

        stage = "ensure_asset_id"
        print("[USECASE] asset_id 보장 시작")
        if not job.asset_id:
            job.asset_id = self._generate_asset_id()
            await self.job_store.save(job)
            print(f"[USECASE] asset_id 생성 완료 asset_id={job.asset_id}")
        else:
            print(f"[USECASE] 기존 asset_id 사용 asset_id={job.asset_id}")

        asset_root_path: Path = Path(job.output_dir)
        input_wav_path: Path = Path(job.input_wav_path)

        print("[USECASE] job 조회 완료")
        print(f"[USECASE] input_wav_path={input_wav_path}")
        print(f"[USECASE] asset_root_path={asset_root_path}")

        try:
            stage = "prepare_dirs"
            print("[USECASE] prepare_dirs 시작")
            self._prepare_dirs(asset_root_path)
            print("[USECASE] prepare_dirs 끝")

            stage = "mark_running"
            print("[USECASE] job mark_running 시작")
            job.mark_running()
            await self.job_store.save(job)
            print("[USECASE] job mark_running 끝")

            stage = "demucs"
            print("[USECASE] demucs 시작")
            bass_only_wav_path: Path = await self.demucs_port.split(
                input_wav_path=input_wav_path,
                output_dir=asset_root_path,
                asset_id=job.asset_id,
                setting=DemucsSplitSetting(
                    boosted_volume_db=10.0,
                    demucs_model="htdemucs",
                    overwrite_outputs=True,
                    cleanup_stems=True,
                ),
                dsp=DemucsDspParams(
                    enable_dsp=False,
                    dsp_highpass_hz=40.0,
                    dsp_lowpass_hz=5000.0,
                    dsp_force_mono=True,
                    dsp_compress=True,
                ),
            )
            print("[USECASE] demucs 끝")
            print(f"[USECASE] bass_only_wav_path={bass_only_wav_path}")

            stage = "save_progress_15"
            job.set_progress(progress=15)
            await self.job_store.save(job)
            print("[USECASE] progress 15 저장 끝")

            original_wav_path: Path = input_wav_path

            stage = "basic_pitch_onset"
            print("[USECASE] basic_pitch onset 시작")
            basic_pitch_onset_result: list[BasicPitchNoteEventDTO] = await self.basic_pitch_port.export_onset(
                params=BasicPitchParams(
                    input_wav_path=bass_only_wav_path,
                    output_dir=asset_root_path,
                    asset_id=job.asset_id,
                )
            )
            print("[USECASE] basic_pitch onset 끝")
            print(f"[USECASE] onset count={len(basic_pitch_onset_result)}")

            stage = "basic_pitch_frame"
            print("[USECASE] basic_pitch frame 시작")
            basic_pitch_frame_result: list[BasicPitchFramePitchDTO] = await self.basic_pitch_port.export_frame(
                params=BasicPitchParams(
                    input_wav_path=bass_only_wav_path,
                    output_dir=asset_root_path,
                    asset_id=job.asset_id,
                )
            )
            print("[USECASE] basic_pitch frame 끝")
            print(f"[USECASE] frame count={len(basic_pitch_frame_result)}")

            stage = "save_progress_40"
            job.set_progress(progress=40)
            await self.job_store.save(job)
            print("[USECASE] progress 40 저장 끝")

            stage = "onset_octave"
            print("[USECASE] onset octave 시작")
            onset_octave_notes: list[BasicPitchNoteEventDTO] = self.onset_octave_port.normalize(
                notes=basic_pitch_onset_result,
                params=OnsetPitchOctaveNormalizeParams(
                    alias_semitones=[-24, -12, 0, 12, 24],
                ),
            )
            print("[USECASE] onset octave 끝")
            print(f"[USECASE] onset_octave count={len(onset_octave_notes)}")

            stage = "frame_octave"
            print("[USECASE] frame octave 시작")
            frame_octave_notes: list[BasicPitchFramePitchDTO] = self.frame_octave_port.normalize(
                frames=basic_pitch_frame_result,
                params=FramePitchOctaveNormalizeParams(),
            )
            print("[USECASE] frame octave 끝")
            print(f"[USECASE] frame_octave count={len(frame_octave_notes)}")

            stage = "onset_normalize"
            print("[USECASE] onset normalize 시작")
            onset_normalized_notes: list[BasicPitchNoteEventDTO] = self.onset_normalize_port.normalize(
                notes=onset_octave_notes,
                params=OnsetNormalizeParams(),
            )
            print("[USECASE] onset normalize 끝")
            print(f"[USECASE] onset_normalized count={len(onset_normalized_notes)}")

            stage = "frame_normalize"
            print("[USECASE] frame normalize 시작")
            frame_normalized_notes: list[BasicPitchNoteEventDTO] = self.frame_note_normalize_port.normalize(
                notes=frame_octave_notes,
                params=FramePitchNormalizeParams(),
            )
            print("[USECASE] frame normalize 끝")
            print(f"[USECASE] frame_normalized count={len(frame_normalized_notes)}")

            stage = "bpm"
            print("[USECASE] bpm 시작")
            bpm: int = await self.bpm_port.estimate_bpm(
                input_wav_path=original_wav_path,
                note=onset_normalized_notes,
                start_seconds=0.0,
                duration_seconds=None,
                sr=22050,
            )
            print("[USECASE] bpm 끝")
            print(f"[USECASE] bpm={bpm}")

            stage = "fuse_original_notes"
            print("[USECASE] onset_frame fuse 시작")
            original_notes: list[BasicPitchNoteEventDTO] = self.onset_frame_fuse_port.normalize(
                bpm=float(bpm),
                onset_notes=onset_normalized_notes,
                frame_notes=frame_normalized_notes,
                params=OnsetFrameFuseParams(),
            )
            print("[USECASE] onset_frame fuse 끝")
            print(f"[USECASE] original_notes count={len(original_notes)}")

            stage = "save_progress_65"
            job.set_progress(progress=65)
            await self.job_store.save(job)
            print("[USECASE] progress 65 저장 끝")

            stage = "build_root_notes"
            print("[USECASE] root build 시작")
            root_notes: list[BasicPitchNoteEventDTO] = self.root_tab_build_port.build(
                bpm=float(bpm),
                original_notes=original_notes,
                params=OnsetFrameFuseParams(),
            )
            print("[USECASE] root build 끝")
            print(f"[USECASE] root_notes count={len(root_notes)}")

            stage = "build_candidates"
            print("[USECASE] candidate build 시작")
            candidates: list[list[BassTabCandidateDTO]] = self.bass_tab_candidate_builder_port.build_candidates(
                notes=original_notes,
                params=BassTabCandidateBuildParams(),
            )
            print("[USECASE] candidate build 끝")
            print(f"[USECASE] candidate note count={len(candidates)}")

            stage = "viterbi"
            print("[USECASE] viterbi 시작")
            viterbi_steps: list[BassTabViterbiStepDTO] = self.bass_tab_viterbi_port.decode(
                notes=original_notes,
                candidates=candidates,
                bpm=int(bpm),
                params=BassTabViterbiParams(),
            )
            print("[USECASE] viterbi 끝")
            print(f"[USECASE] viterbi_steps count={len(viterbi_steps)}")

            stage = "generate_original_tab"
            print("[USECASE] original tab 생성 시작")
            original_tab_path: Path = self.original_tab_generate_port.tab_generate(
                original_json=viterbi_steps,
                bpm=int(bpm),
                output_dir=asset_root_path,
                asset_id=job.asset_id,
            )
            print("[USECASE] original tab 생성 끝")
            print(f"[USECASE] original_tab_path={original_tab_path}")

            stage = "generate_root_tab"
            print("[USECASE] root tab 생성 시작")
            root_tab_path: Path = self.root_tab_generate_adapter.tab_generate(
                original_json=root_notes,
                bpm=int(bpm),
                output_dir=asset_root_path,
                asset_id=job.asset_id,
            )
            print("[USECASE] root tab 생성 끝")
            print(f"[USECASE] root_tab_path={root_tab_path}")

            stage = "mark_done"
            print("[USECASE] job mark_done 시작")
            job.mark_done()
            await self.job_store.save(job)
            print("[USECASE] job mark_done 끝")

            print("[USECASE] 전체 완료")
            return MLProcessResponseDTO(
                job_id=job.job_id,
                song_id=job.song_id,
                result_id=job.result_id,
                asset_id=job.asset_id,
                status=job.status.value,
                path=str(asset_root_path),
                error=None,
                norm_title=request.norm_title,
                norm_artist=request.norm_artist,
            )

        except Exception as e:
            print(f"[USECASE] 예외 발생 stage={stage}")
            print(f"[USECASE] 예외 내용={e}")

            try:
                print("[USECASE] job mark_failed 시작")
                job.mark_failed(error=str(e))
                await self.job_store.save(job)
                print("[USECASE] job mark_failed 끝")
            except Exception as save_e:
                print(f"[USECASE] mark_failed 저장 중 추가 예외={save_e}")

            return MLProcessResponseDTO(
                job_id=job.job_id,
                song_id=job.song_id,
                result_id=job.result_id,
                asset_id=job.asset_id,
                status="failed",
                path=str(asset_root_path),
                error=f"[stage={stage}] {e}",
                norm_title=request.norm_title,
                norm_artist=request.norm_artist,
            )

    async def _get_job(self, job_id: str) -> MLJob:
        job: MLJob | None = await self.job_store.get(job_id)
        if job is None:
            raise ValueError(f"job not found: {job_id}")
        return job

    def _generate_asset_id(self) -> str:
        return f"asset_{uuid.uuid4().hex}"

    def _prepare_dirs(self, asset_root_path: Path) -> None:
        asset_root_path.mkdir(parents=True, exist_ok=True)
        (asset_root_path / "audio").mkdir(parents=True, exist_ok=True)
        (asset_root_path / "note").mkdir(parents=True, exist_ok=True)
        (asset_root_path / "tab").mkdir(parents=True, exist_ok=True)
        (asset_root_path / "meta").mkdir(parents=True, exist_ok=True)

    def _save_note_events(
        self,
        *,
        output_path: Path,
        notes: list[BasicPitchNoteEventDTO],
    ) -> None:
        payload: list[dict[str, float | int | None]] = [
            {
                "start_time": float(n.start_time),
                "end_time": float(n.end_time),
                "pitch_midi": int(n.pitch_midi),
                "confidence": None if n.confidence is None else float(n.confidence),
            }
            for n in notes
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_viterbi_steps(
        self,
        *,
        output_path: Path,
        steps: list[BassTabViterbiStepDTO],
    ) -> None:
        payload: list[dict[str, float | int]] = [
            {
                "note_index": int(s.note_index),
                "pitch_midi": int(s.pitch_midi),
                "start_time": float(s.start_time),
                "end_time": float(s.end_time),
                "line": int(s.line),
                "fret": int(s.fret),
            }
            for s in steps
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )