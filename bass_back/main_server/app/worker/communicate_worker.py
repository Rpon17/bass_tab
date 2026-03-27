from __future__ import annotations

import asyncio
import os
import signal
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as redis
from dotenv import load_dotenv

# .env 로드
load_dotenv()

from app.adapters.jobs.job_store_redis import RedisJobStore
from app.domain.jobs_domain import JobStatus
from app.application.usecases.songs.asset_create_usecase import CreateAssetUseCase

def _log(message: str) -> None:
    print(f"[watchdog-worker] {message}")

@dataclass(frozen=True)
class CommunicaterConfig:
    redis_url: str
    key_prefix: str = "bass:"
    submitted_sample_n: int = 20
    poll_interval_seconds: float = 5.0  # 감시 주기는 조금 여유 있게 (5초)
    submitted_timeout_minutes: int = 15 # 15분 이상 응답 없으면 실패 처리
    job_ttl_seconds: int = 60 * 60     # 결과 유지 시간 (1시간)
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

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _to_datetime_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except: return _utcnow()
    return _utcnow()

def _is_submitted_timeout(updated_at: Any, timeout_minutes: int) -> bool:
    if timeout_minutes <= 0: return False
    updated_at_dt = _to_datetime_utc(updated_at)
    return _utcnow() >= (updated_at_dt + timedelta(minutes=timeout_minutes))

async def _watchdog_one(
    *,
    job_id: str,
    store: RedisJobStore,
    cfg: CommunicaterConfig,
    sem: asyncio.Semaphore,
) -> None:
    """
    HTTP 호출 없이 Redis에 저장된 Job 상태만 확인합니다.
    """
    async with sem:
        job = await store.get(job_id=job_id)
        
        # 1. Redis에 Job 데이터 자체가 없는 경우
        if not job:
            _log(f"Job data missing in Redis, removing from queue: {job_id}")
            await store.remove_submitted(job_id)
            return

        # 2. 이미 성공(DONE)했거나 실패(FAILED)한 경우
        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            _log(f"Job {job_id} is already {job.status}. Clearing from submitted list.")
            await store.remove_submitted(job_id)
            return

        # 3. 아직 진행 중인데 너무 오래 걸리는 경우 (타임아웃 처리)
        if _is_submitted_timeout(job.updated_at, cfg.submitted_timeout_minutes):
            _log(f"⚠️ Job Timeout Detect: {job_id} (No response for {cfg.submitted_timeout_minutes}m)")
            job.mark_failed(error=f"Processing timeout after {cfg.submitted_timeout_minutes} minutes.")
            await store.save(job=job, ttl_seconds=cfg.job_ttl_seconds)
            await store.remove_submitted(job_id)
            return
        
        # 아직 정상 범위 내에서 분석 중인 경우 아무것도 하지 않음 (Pass)

async def watchdog_loop(
    cfg: CommunicaterConfig,
) -> None:
    _log("🚀 Watchdog worker started (Monitoring Redis status)")

    r: redis.Redis = redis.from_url(cfg.redis_url, decode_responses=True)
    await r.ping()
    store: RedisJobStore = RedisJobStore(r, key_prefix=cfg.key_prefix)

    shutdown = GracefulShutdown()
    shutdown.install()
    sem = asyncio.Semaphore(cfg.max_concurrent_status_checks)

    try:
        while not shutdown.stop_event.is_set():
            # 제출된(Submitted) 리스트에서 작업 ID 샘플링
            job_ids = await store.sample_submitted(cfg.submitted_sample_n)

            if job_ids:
                tasks = [
                    asyncio.create_task(_watchdog_one(
                        job_id=job_id, store=store, cfg=cfg, sem=sem
                    )) for job_id in job_ids
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(cfg.poll_interval_seconds)
    finally:
        await r.aclose()
        _log("Watchdog worker stopped.")

def build_config() -> CommunicaterConfig:
    return CommunicaterConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("REDIS_KEY_PREFIX", "bass:"),
        submitted_sample_n=int(os.getenv("COMM_SUBMITTED_SAMPLE_N", "20")),
        poll_interval_seconds=float(os.getenv("COMM_POLL_INTERVAL_SECONDS", "5.0")),
        submitted_timeout_minutes=int(os.getenv("COMM_SUBMITTED_TIMEOUT_MINUTES", "15")),
        job_ttl_seconds=int(os.getenv("COMM_JOB_TTL_SECONDS", "3600")),
    )

async def main() -> None:
    cfg = build_config()
    await watchdog_loop(cfg=cfg)

if __name__ == "__main__":
    asyncio.run(main())