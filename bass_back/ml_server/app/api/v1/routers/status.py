from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
import redis.asyncio as redis

from app.adapters.job.job_store_redis import RedisJobStore
from app.domain.jobs_domain import MLJobStatus
from app.domain.models_domain import MLJob

router: APIRouter = APIRouter(prefix="/v1", tags=["ml-status"])


async def get_redis() -> redis.Redis:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print("[ml-status] redis_url =", redis_url)
    return redis.from_url(redis_url)


@router.get("/status/{job_id}")
async def get_status(
    job_id: str,
    r: redis.Redis = Depends(get_redis),
) -> dict[str, object]:
    prefix: str = os.getenv("ML_JOB_KEY_PREFIX", "bass:ml:")
    print("[ml-status] called")
    print("[ml-status] job_id =", job_id)
    print("[ml-status] prefix =", prefix)

    store: RedisJobStore = RedisJobStore(
        r,
        key_prefix=prefix,
    )

    job: MLJob | None = await store.get(job_id)
    print("[ml-status] job =", job)

    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    return {
        "job_id": job.job_id,
        "song_id": job.song_id,
        "result_id": job.result_id,
        "asset_id": job.asset_id,
        "status": job.status.value if isinstance(job.status, MLJobStatus) else str(job.status),
        "path": str(job.output_dir),
        "error": job.error,
    }