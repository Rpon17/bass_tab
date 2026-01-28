# worker/ml_worker.py
from __future__ import annotations

import asyncio
import os
import signal
import uuid
from dataclasses import dataclass
from pathlib import Path

import redis.asyncio as redis

from bass_back.main_server.app.domain.jobs_domain import JobStatus
from bass_back.main_server.app.adapters.jobs.job_store_redis import RedisJobStore
from worker.ml_client import MLHttpClient, Mode


@dataclass(frozen=True)
class MLWorkerConfig:
    redis_url: str
    key_prefix: str = "job:"
    submitted_queue_name: str = "submitted"
    job_ttl_seconds: int = 60 * 30
    lock_ttl_seconds: int = 60 * 10

    ml_base_url: str = "http://127.0.0.1:8001"
    ml_timeout_sec: float = 120.0
    mode: Mode = "full"


class GracefulShutdown:
    def __init__(self) -> None:
        self._stop = asyncio.Event()

    def install(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: self._stop.set())

    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop


async def process_one_submitted_job(
    *,
    job_id: str,
    store: RedisJobStore,
    ml: MLHttpClient,
    cfg: MLWorkerConfig,
) -> None:
    job = await store.get(job_id)
    if not job:
        return

    # SUBMITTED 상태인 것만 처리
    if job.status != JobStatus.SUBMITTED:
        return

    token = uuid.uuid4().hex
    locked = False

    try:
        locked = await store.acquire_lock(job_id, token=token, ttl_seconds=cfg.lock_ttl_seconds)
        if not locked:
            return

        # 최신 상태 재검증
        job = await store.get(job_id)
        if not job or job.status != JobStatus.SUBMITTED:
            return

        # input_wav_path 필수
        if not job.input_wav_path:
            job.mark_failed(error="missing input_wav_path")
            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
            return

        # (선택) ML단계 RUNNING 표시
        job.mark_running()
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

        # ML 서버 호출
        resp = await ml.process(
            job_id=job_id,
            input_wav_path=job.input_wav_path,
            mode=cfg.mode,
            meta={"source": "ml_worker"},
        )

        if not resp.ok or not resp.result:
            job.mark_failed(error=resp.error or "ml_server failed")
            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
            return

        # 결과 반영(너의 Job 도메인에 맞게 필드명을 매핑)
        # 예: job.result_path / job.bpm / job.notes / job.tabs 등
        # 지금 Job에 어떤 필드가 있는지에 따라 여기 조정.
        #
        # 최소한 결과 파일 경로 같은 걸 저장하는 방향 추천.
        # 여기서는 예시로 result_path에 bass_wav_path를 넣음.
        if resp.result.bass_wav_path:
            job.result_path = resp.result.bass_wav_path

        # DONE 처리
        job.mark_done(result_path=job.result_path or "")
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

    except Exception as e:
        # 예외면 실패 처리
        try:
            job = await store.get(job_id) or job
            job.mark_failed(error=str(e))
            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
        except Exception:
            pass

    finally:
        if locked:
            try:
                await store.release_lock(job_id, token=token)
            except Exception:
                pass


async def ml_worker_loop(cfg: MLWorkerConfig) -> None:
    r = redis.from_url(cfg.redis_url)
    await r.ping()

    store = RedisJobStore(r, key_prefix=cfg.key_prefix)
    ml = MLHttpClient(base_url=cfg.ml_base_url, timeout_sec=cfg.ml_timeout_sec)

    shutdown = GracefulShutdown()
    shutdown.install()

    try:
        while not shutdown.stop_event.is_set():
            # submitted 큐에서 pop (RedisJobStore에 dequeue_submitted를 만들었으면 그걸 쓰는 게 더 깔끔)
            job_id = await store.dequeue(cfg.submitted_queue_name, timeout_seconds=3)
            if not job_id:
                continue

            await process_one_submitted_job(job_id=job_id, store=store, ml=ml, cfg=cfg)

    finally:
        await ml.aclose()
        await r.aclose()


def main() -> None:
    cfg = MLWorkerConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("JOB_KEY_PREFIX", "job:"),
        ml_base_url=os.getenv("ML_BASE_URL", "http://127.0.0.1:8001"),
        mode=os.getenv("ML_MODE", "full"),  # "full" etc
    )
    asyncio.run(ml_worker_loop(cfg))


if __name__ == "__main__":
    main()
