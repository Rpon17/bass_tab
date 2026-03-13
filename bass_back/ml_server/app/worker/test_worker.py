from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass

import redis.asyncio as redis

from app.adapters.job.job_store_redis import RedisJobStore
from app.application.usecases.final_usecase import RunMLProcessUseCase
from app.domain.jobs_domain import MLJobStatus
from app.domain.models_domain import MLJob
from shared.dtos.main_ml_dto import MLProcessRequestDTO

""" 
    demucs만 가짜를 쓰고있음
"""
QUEUE_NAME: str = "ml:process"


@dataclass(frozen=True)
class MLWorkerConfig:
    redis_url: str
    key_prefix: str = "bass:ml:"
    queue_name: str = QUEUE_NAME
    job_ttl_seconds: int = 60 * 60


class GracefulShutdown:
    def __init__(self) -> None:
        self._stop: asyncio.Event = asyncio.Event()

    def install(self) -> None:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: self._stop.set())

    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop


def build_usecase(*, store: RedisJobStore) -> RunMLProcessUseCase:
    from app.adapters.bpm.bpm_estimate_adapter import LibrosaBpmEstimator
    from app.adapters.demucs.fake_demucs_adapter import FakeDemucsAdapter
    from app.adapters.basic_pitch.basic_pitch_adapter import BasicPitchAdapter

    from app.adapters.tab.frame.frame_octave_adapter import FramePitchOctaveNormalizeAdapter
    from app.adapters.tab.frame.frame_json_normalization_adapter import FramePitchNormalizeAdapter

    from app.adapters.tab.onset.onset_octave_adapter import OnsetPitchOctaveNormalizeAdapter
    from app.adapters.tab.onset.onset_json_normalization_adapter import OnsetNormalizeAdapter

    from app.adapters.tab.merge.original.onset_frame_plus_adapter import OnsetFrameFuseAdapter
    from app.adapters.tab.merge.root.root_note_adapter import RootTabBuildAdapter

    from app.adapters.tab.tab.origianal_tab.candidate_adapter import BassTabCandidateBuilderAdapter
    from app.adapters.tab.tab.origianal_tab.viterbi_adapter import BassTabViterbiAdapter
    from app.adapters.tab.tab.origianal_tab.original_tab_adapter import OriginalTabGenerateAdapter
    from app.adapters.tab.tab.root_tab.root_tab_adapter import RootTabGenerateAdapter

    candidate_builder: BassTabCandidateBuilderAdapter = BassTabCandidateBuilderAdapter()
    viterbi: BassTabViterbiAdapter = BassTabViterbiAdapter()

    original_tab_generator: OriginalTabGenerateAdapter = OriginalTabGenerateAdapter(
        candidate_builder=candidate_builder,
        viterbi=viterbi,
    )

    root_tab_generator: RootTabGenerateAdapter = RootTabGenerateAdapter(
        candidate_builder=candidate_builder,
    )

    return RunMLProcessUseCase(
        job_store=store,
        bpm_port=LibrosaBpmEstimator(),
        demucs_port=FakeDemucsAdapter(fake_delay_seconds=0.0),
        basic_pitch_port=BasicPitchAdapter(),
        frame_octave_port=FramePitchOctaveNormalizeAdapter(),
        frame_note_normalize_port=FramePitchNormalizeAdapter(),
        onset_octave_port=OnsetPitchOctaveNormalizeAdapter(),
        onset_normalize_port=OnsetNormalizeAdapter(),
        onset_frame_fuse_port=OnsetFrameFuseAdapter(),
        root_tab_build_port=RootTabBuildAdapter(),
        bass_tab_candidate_builder_port=candidate_builder,
        bass_tab_viterbi_port=viterbi,
        original_tab_generate_port=original_tab_generator,
        root_tab_generate_adapter=root_tab_generator,
    )


async def process_one_job(
    *,
    job_id: str,
    store: RedisJobStore,
    usecase: RunMLProcessUseCase,
    cfg: MLWorkerConfig,
) -> None:
    job: MLJob | None = await store.get(job_id)
    if job is None:
        print(f"[ml-worker-test] skip: job not found job_id={job_id}")
        return

    if job.status != MLJobStatus.QUEUED:
        print(f"[ml-worker-test] skip: invalid status job_id={job_id} status={job.status}")
        return

    try:
        latest_job: MLJob | None = await store.get(job_id)
        if latest_job is None:
            print(f"[ml-worker-test] skip: latest job not found job_id={job_id}")
            return

        if latest_job.status != MLJobStatus.QUEUED:
            print(f"[ml-worker-test] skip: latest invalid status job_id={job_id} status={latest_job.status}")
            return

        request: MLProcessRequestDTO = MLProcessRequestDTO(
            job_id=latest_job.job_id,
            song_id=latest_job.song_id,
            result_id=latest_job.result_id,
            input_wav_path=str(latest_job.input_wav_path),
            result_path=str(latest_job.result_path),
            norm_title=latest_job.norm_title,
            norm_artist=latest_job.norm_artist,
        )

        print(f"[ml-worker-test] start job_id={latest_job.job_id}")
        print(f"[ml-worker-test] input_wav_path={latest_job.input_wav_path}")
        print(f"[ml-worker-test] result_path={latest_job.result_path}")

        response = await usecase.execute(request=request)

        print(f"[ml-worker-test] done job_id={response.job_id} status={response.status}")

    except Exception as e:
        print(f"[ml-worker-test] exception job_id={job_id} error={e}")

        try:
            failed_job: MLJob | None = await store.get(job_id)
            if failed_job is not None:
                failed_job.mark_failed(error=str(e))
                await store.save(failed_job, ttl_seconds=cfg.job_ttl_seconds)
        except Exception as save_e:
            print(f"[ml-worker-test] save fail error={save_e}")


async def worker_loop(cfg: MLWorkerConfig) -> None:
    r: redis.Redis = redis.from_url(cfg.redis_url)
    await r.ping()

    store: RedisJobStore = RedisJobStore(r, key_prefix=cfg.key_prefix)
    usecase: RunMLProcessUseCase = build_usecase(store=store)

    shutdown: GracefulShutdown = GracefulShutdown()
    shutdown.install()

    try:
        while not shutdown.stop_event.is_set():
            job_id: str | None = await store.dequeue(cfg.queue_name, timeout_seconds=3)
            if job_id is None:
                continue

            await process_one_job(
                job_id=job_id,
                store=store,
                usecase=usecase,
                cfg=cfg,
            )
    finally:
        await r.aclose()


def main() -> None:
    cfg: MLWorkerConfig = MLWorkerConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("ML_JOB_KEY_PREFIX", "bass:ml:"),
        queue_name=os.getenv("ML_QUEUE_NAME", QUEUE_NAME),
        job_ttl_seconds=int(os.getenv("JOB_TTL_SECONDS", "3600")),
    )

    print("[ml-worker-test] redis_url:", cfg.redis_url)
    print("[ml-worker-test] key_prefix:", cfg.key_prefix)
    print("[ml-worker-test] queue_name:", cfg.queue_name)

    asyncio.run(worker_loop(cfg))


if __name__ == "__main__":
    main()