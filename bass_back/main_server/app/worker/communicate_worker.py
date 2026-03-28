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
    # ⌚ 시간 정보 추가로 로그 가독성 향상
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}][communicate-worker] {message}")

@dataclass(frozen=True)
class CommunicaterConfig:
    redis_url: str
    key_prefix: str = "bass:"
    submitted_sample_n: int = 10
    poll_interval_seconds: float = 5.0  
    submitted_timeout_minutes: int = 15 
    job_ttl_seconds: int = 60 * 60    
    max_concurrent_status_checks: int = 10

class GracefulShutdown:
    def __init__(self) -> None:
        self._stop: asyncio.Event = asyncio.Event()

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

async def _process_one_job(
    *,
    job_id: str,
    store: RedisJobStore,
    cfg: CommunicaterConfig,
    sem: asyncio.Semaphore,
    create_asset_uc: CreateAssetUseCase, # UseCase 추가
) -> None:
    async with sem:
        job = await store.get_ml(job_id=job_id)
        
        # 1. Redis에 Job 데이터 자체가 없는 경우
        if not job:
            _log(f"❌ Job data missing in Redis: {job_id}. Removing from queue.")
            await store.remove_submitted(job_id)
            return

        # 2. 작업 완료 처리 (DONE 상태인 경우)
    
        if job.status == JobStatus.DONE:
            ml_data = await store._r.hgetall(f"bass:ml:job:{job_id}")
            _log(f"✅ Job {job_id} is DONE. Finalizing asset creation...")
            try:
                await create_asset_uc.execute(
                    result_id=ml_data.get("result_id"),
                    asset_id=ml_data.get("asset_id"),
                    path=ml_data.get("result_path")
                    )
                _log(f"🎉 Asset created for Job {job_id}.")
                
                await store.remove_submitted(job_id)
            except Exception as e:
                _log(f"⚠️ Failed to finalize asset for {job_id}: {e}")
            return

        if job.status == JobStatus.FAILED:
            _log(f"ℹ️ Job {job_id} is already FAILED. Clearing from submitted list.")
            await store.remove_submitted(job_id)
            return

        if _is_submitted_timeout(job.updated_at, cfg.submitted_timeout_minutes):
            _log(f"⚠️ Job Timeout Detect: {job_id} (No response for {cfg.submitted_timeout_minutes}m)")
            job.mark_failed(error=f"Processing timeout after {cfg.submitted_timeout_minutes} minutes.")
            await store.save(job=job, ttl_seconds=cfg.job_ttl_seconds)
            await store.remove_submitted(job_id)
            return
        

async def worker_loop(
    cfg: CommunicaterConfig,
    create_asset_uc: CreateAssetUseCase,
) -> None:
    _log(f"🚀 Communicate worker started (Prefix: {cfg.key_prefix})")

    r: redis.Redis = redis.from_url(cfg.redis_url, decode_responses=True)
    await r.ping()
    store: RedisJobStore = RedisJobStore(r, key_prefix=cfg.key_prefix)

    shutdown = GracefulShutdown()
    shutdown.install()
    sem = asyncio.Semaphore(cfg.max_concurrent_status_checks)

    try:
        while not shutdown.stop_event.is_set():
            job_ids = await store.sample_submitted(cfg.submitted_sample_n)

            if job_ids:
                _log(f"🔎 감시 중인 작업 목록 ({len(job_ids)}개): {job_ids}")
                
                tasks = [
                    asyncio.create_task(_process_one_job(
                        job_id=job_id, 
                        store=store, 
                        cfg=cfg, 
                        sem=sem,
                        create_asset_uc=create_asset_uc
                    )) for job_id in job_ids
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                pass
            await asyncio.sleep(cfg.poll_interval_seconds)
    finally:
        await r.aclose()
        _log("Communicate worker stopped.")


def build_config() -> CommunicaterConfig:
    redis_url = os.getenv("REDIS_URL")
    return CommunicaterConfig(
        redis_url=redis_url,
        key_prefix=os.getenv("REDIS_KEY_PREFIX", "bass:"),
        submitted_sample_n=int(os.getenv("COMM_SUBMITTED_SAMPLE_N", "20")),
        poll_interval_seconds=float(os.getenv("COMM_POLL_INTERVAL_SECONDS", "5.0")),
        submitted_timeout_minutes=int(os.getenv("COMM_SUBMITTED_TIMEOUT_MINUTES", "15")),
        job_ttl_seconds=int(os.getenv("COMM_JOB_TTL_SECONDS", "3600")),
    )

async def main() -> None:
    from app.api.v1.deps import get_create_asset_uc 
    
    cfg = build_config()
    create_asset_uc = get_create_asset_uc()
    
    await worker_loop(cfg=cfg, create_asset_uc=create_asset_uc)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass