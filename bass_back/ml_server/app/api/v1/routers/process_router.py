from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
import redis.asyncio as redis

from app.adapters.job.job_store_redis import RedisJobStore
from app.domain.jobs_domain import MLJobStatus
from app.domain.models_domain import MLJob
from shared.dtos.main_ml_dto import MLProcessRequestDTO, MLProcessResponseDTO


router: APIRouter = APIRouter(prefix="/v1", tags=["ml-process"])

QUEUE_NAME: str = "ml:process"


async def get_redis() -> redis.Redis:
    print("[ml-process] get_redis called")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print("[ml-process] redis url =", redis_url)
    return redis.from_url(redis_url)


@router.post("/process", response_model=MLProcessResponseDTO)
async def submit_process(
    request: MLProcessRequestDTO,
    r: redis.Redis = Depends(get_redis),
) -> MLProcessResponseDTO:
    print("\n==============================")
    print("[ml-process] submit_process entered")
    print("[ml-process] request =", request.model_dump())

    store: RedisJobStore = RedisJobStore(
        r,
        key_prefix=os.getenv("ML_JOB_KEY_PREFIX", "bass:ml:"),
    )

    print("[ml-process] checking existing job:", request.job_id)

    existing: MLJob | None = await store.get(request.job_id)

    result_path: Path = Path(request.result_path).resolve()
    print("[ml-process] result_path =", result_path)

    output_dir: Path = result_path
    print("[ml-process] output_dir =", output_dir)

    input_wav: Path = Path(request.input_wav_path).resolve()
    print("[ml-process] input_wav_path =", input_wav)

    if existing is not None:
        print("[ml-process] job already exists:", request.job_id)

        response_asset_id: str = existing.asset_id or ""
        response_path: str = existing.output_dir or str(output_dir)

        return MLProcessResponseDTO(
            job_id=existing.job_id,
            song_id=existing.song_id,
            result_id=existing.result_id,
            asset_id=response_asset_id,
            status=existing.status.value if isinstance(existing.status, MLJobStatus) else str(existing.status),
            path=response_path,
            error=existing.error,
        )

    print("[ml-process] job not found, creating new")

    asset_id: str = uuid.uuid4().hex
    print("[ml-process] generated asset_id =", asset_id)

    now: datetime = datetime.utcnow()

    job: MLJob = MLJob(
        job_id=request.job_id,
        song_id=request.song_id,
        result_id=request.result_id,
        input_wav_path=str(input_wav),
        output_dir=str(output_dir),
        result_path=str(result_path),
        asset_id=asset_id,
        status=MLJobStatus.QUEUED,
        progress=0,
        error=None,
        norm_title=request.norm_title,
        norm_artist=request.norm_artist,
        created_at=now,
        updated_at=now,
    )
    
    print("[ml-process] MLJob object created")
    print("[ml-process] job =", job)
    print("[ml-process] job.output_dir =", job.output_dir)
    print("[ml-process] job.result_path =", job.result_path)

    print("[ml-process] before store.create")
    await store.create(job, ttl_seconds=60 * 60)
    print("[ml-process] after store.create")

    print("[ml-process] before enqueue:", QUEUE_NAME)
    await store.enqueue(QUEUE_NAME, request.job_id)
    print("[ml-process] after enqueue")

    print("[ml-process] returning response")

    return MLProcessResponseDTO(
        job_id=job.job_id,
        song_id=job.song_id,
        result_id=job.result_id,
        asset_id=job.asset_id or "",
        status=job.status.value if isinstance(job.status, MLJobStatus) else str(job.status),
        path=str(output_dir),
        error=None,
    )