# main_server/app/worker/communicate_worker.py
from __future__ import annotations

import asyncio
import os
import signal
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import redis.asyncio as redis

from app.adapters.jobs.job_store_redis import RedisJobStore
from app.domain.jobs_domain import JobStatus
from app.application.usecases.songs.asset_create_usecase import CreateAssetUseCase
from shared.dtos.ml_ml_dto import MLProcessResponseDTO


def _log(message: str) -> None:
    print(f"[communicate-worker] {message}")


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


def _to_datetime_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, str):
        s: str = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        try:
            dt: datetime = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return _utcnow()

    return _utcnow()


def _is_submitted_timeout(
    *,
    updated_at: Any,
    timeout_minutes: int,
) -> bool:
    if timeout_minutes <= 0:
        return False

    updated_at_dt: datetime = _to_datetime_utc(updated_at)
    deadline: datetime = updated_at_dt + timedelta(minutes=timeout_minutes)
    return _utcnow() >= deadline


async def _communicater_one(
    *,
    job_id: str,
    store: RedisJobStore,
    ml: MLStatusClient,
    cfg: CommunicaterConfig,
    sem: asyncio.Semaphore,
    create_asset_uc: CreateAssetUseCase,
) -> None:
    async with sem:
        job = await store.get(job_id=job_id)
        if not job:
            _log(f"job not found in redis: {job_id}")
            await store.remove_submitted(job_id)
            return

        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            await store.remove_submitted(job_id)
            return

        try:
            data: MLProcessResponseDTO = await ml.get_status(job_id)
            _log(f"ML status response: job_id={job_id} status={data.status}")
        except Exception as e:
            _log(f"ML status request failed: {job_id} error={repr(e)}")
            traceback.print_exc()

            if _is_submitted_timeout(
                updated_at=job.updated_at,
                timeout_minutes=cfg.submitted_timeout_minutes,
            ):
                job.mark_failed(error=f"ML status polling timeout: {e}")
                await store.save(job=job, ttl_seconds=cfg.job_ttl_seconds)
                await store.remove_submitted(job_id)
            return

        status: str = data.status.lower().strip()

        if status == "done":
            result_path: str = data.path
            asset_id: str = data.asset_id
            result_id: str | None = job.result_id

            _log(f"ML done received: job_id={job_id}")
            _log(f"result_path={result_path}")
            _log(f"asset_id={asset_id}")
            _log(f"result_id={result_id}")

            if result_path and asset_id and result_id:
                try:
                    _log("calling create_asset_uc.execute()")

                    await create_asset_uc.execute(
                        result_id=result_id,
                        asset_id=asset_id,
                        path=result_path,
                    )

                    job.asset_id = asset_id
                    job.mark_done(path=result_path)
                    _log(f"job done: {job_id}")

                except Exception as e:
                    _log("asset save failed !!!")
                    _log(f"job_id={job_id}")
                    _log(f"result_id={result_id}")
                    _log(f"asset_id={asset_id}")
                    _log(f"path={result_path}")
                    _log(f"error={repr(e)}")
                    traceback.print_exc()

                    job.mark_failed(error=f"Asset save failed: {e}")
            else:
                _log("ML returned invalid done payload")
                job.mark_failed(
                    error="ML returned done but missing path/asset_id/result_id"
                )

            await store.save(job=job, ttl_seconds=cfg.job_ttl_seconds)
            await store.remove_submitted(job_id)
            return

        if status == "failed":
            err: str = data.error or "ML processing failed"
            _log(f"ML job failed: {job_id} error={err}")

            job.mark_failed(error=err)
            await store.save(job=job, ttl_seconds=cfg.job_ttl_seconds)
            await store.remove_submitted(job_id)
            return


async def communicater_loop(
    cfg: CommunicaterConfig,
    create_asset_uc: CreateAssetUseCase,
) -> None:
    _log("starting communicate worker")

    r: redis.Redis = redis.from_url(cfg.redis_url)
    await r.ping()
    _log(f"redis connected: {cfg.redis_url}")

    store: RedisJobStore = RedisJobStore(r, key_prefix=cfg.key_prefix)

    ml: MLStatusClient = MLStatusClient(
        cfg.ml_server_base_url,
        timeout_seconds=cfg.http_timeout_seconds,
    )

    _log(f"ml server base url: {cfg.ml_server_base_url}")

    shutdown: GracefulShutdown = GracefulShutdown()
    shutdown.install()

    sem: asyncio.Semaphore = asyncio.Semaphore(cfg.max_concurrent_status_checks)

    try:
        while not shutdown.stop_event.is_set():

            job_ids: list[str] = await store.sample_submitted(cfg.submitted_sample_n)

            if job_ids:
                _log(f"submitted jobs found: {len(job_ids)}")

                tasks: list[asyncio.Task[None]] = [
                    asyncio.create_task(
                        _communicater_one(
                            job_id=job_id,
                            store=store,
                            ml=ml,
                            cfg=cfg,
                            sem=sem,
                            create_asset_uc=create_asset_uc,
                        )
                    )
                    for job_id in job_ids
                ]

                await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(cfg.poll_interval_seconds)

    finally:
        await ml.aclose()
        await r.aclose()
        _log("worker stopped")


def build_config() -> CommunicaterConfig:
    return CommunicaterConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("REDIS_KEY_PREFIX", "bass:"),
        submitted_sample_n=int(os.getenv("COMM_SUBMITTED_SAMPLE_N", "20")),
        poll_interval_seconds=float(os.getenv("COMM_POLL_INTERVAL_SECONDS", "2.0")),
        submitted_timeout_minutes=int(os.getenv("COMM_SUBMITTED_TIMEOUT_MINUTES", "30")),
        job_ttl_seconds=int(os.getenv("COMM_JOB_TTL_SECONDS", str(60 * 30))),
        ml_server_base_url=os.getenv("ML_SERVER_BASE_URL", "http://localhost:8001"),
        http_timeout_seconds=float(os.getenv("COMM_HTTP_TIMEOUT_SECONDS", "10.0")),
        max_concurrent_status_checks=int(
            os.getenv("COMM_MAX_CONCURRENT_STATUS_CHECKS", "10")
        ),
    )


async def main() -> None:
    from app.api.v1.deps import get_create_asset_uc

    cfg: CommunicaterConfig = build_config()
    create_asset_uc: CreateAssetUseCase = get_create_asset_uc()

    await communicater_loop(
        cfg=cfg,
        create_asset_uc=create_asset_uc,
    )


if __name__ == "__main__":
    asyncio.run(main())
