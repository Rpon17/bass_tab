from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
import redis.asyncio as redis

from app.adapters.jobs.job_store_redis import RedisJobStore
from app.domain.jobs_domain import JobStatus
from app.application.usecases.songs.asset_create_usecase import CreateResultUseCase
from shared.dtos.ml_ml_dto import MLProcessResponseDTO


@dataclass(frozen=True)
class CommunicaterConfig:
    redis_url: str
    key_prefix: str = "bass:"
    submitted_sample_n: int = 20
    poll_interval_seconds: float = 2.0
    submitted_timeout_minutes: int = 30
    job_ttl_seconds: int = 60 * 30
    ml_server_base_url: str = "http://localhost:8001"
    http_timeout_seconds: float = 10.0
    max_concurrent_status_checks: int = 10


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


class MLStatusClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 10.0) -> None:
        self._base_url: str = base_url.rstrip("/")
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_status(self, job_id: str) -> MLProcessResponseDTO:
        url: str = f"{self._base_url}/v1/status/{job_id}"
        response: httpx.Response = await self._client.get(url)
        response.raise_for_status()
        return MLProcessResponseDTO.model_validate(response.json())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _communicater_one(
    *,
    job_id: str,
    store: RedisJobStore,
    ml: MLStatusClient,
    cfg: CommunicaterConfig,
    sem: asyncio.Semaphore,
    create_result_uc: CreateResultUseCase,
) -> None:
    async with sem:
        job = await store.get(job_id)
        if not job:
            await store.remove_submitted(job_id)
            return

        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            await store.remove_submitted(job_id)
            return

        try:
            data: MLProcessResponseDTO = await ml.get_status(job_id)
        except Exception:
            return

        status: str = data.status.lower().strip()

        if status == "done":
            result_path: str = data.path
            asset_id: str = data.asset_id
            result_id: str | None = job.result_id

            if result_path and asset_id and result_id:
                await create_result_uc.execute(
                    result_id=result_id,
                    asset_id=asset_id,
                    path=result_path,
                )
                job.asset_id = asset_id
                job.mark_done(path=result_path)
            else:
                job.mark_failed(
                    error="ML returned done but missing path/asset_id/result_id"
                )

            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
            await store.remove_submitted(job_id)
            return

        if status == "failed":
            err: str = data.error or "ML processing failed"
            job.mark_failed(error=err)
            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
            await store.remove_submitted(job_id)
            return


async def communicater_loop(
    cfg: CommunicaterConfig,
    create_result_uc: CreateResultUseCase,
) -> None:
    r: redis.Redis = redis.from_url(cfg.redis_url)
    await r.ping()

    store: RedisJobStore = RedisJobStore(r, key_prefix=cfg.key_prefix)
    ml: MLStatusClient = MLStatusClient(
        cfg.ml_server_base_url,
        timeout_seconds=cfg.http_timeout_seconds,
    )

    shutdown: GracefulShutdown = GracefulShutdown()
    shutdown.install()

    sem: asyncio.Semaphore = asyncio.Semaphore(cfg.max_concurrent_status_checks)

    try:
        while not shutdown.stop_event.is_set():
            job_ids: list[str] = await store.sample_submitted(cfg.submitted_sample_n)

            if job_ids:
                tasks: list[asyncio.Future[None] | asyncio.Task[None]] = [
                    _communicater_one(
                        job_id=job_id,
                        store=store,
                        ml=ml,
                        cfg=cfg,
                        sem=sem,
                        create_result_uc=create_result_uc,
                    )
                    for job_id in job_ids
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(cfg.poll_interval_seconds)
    finally:
        await ml.aclose()
        await r.aclose()