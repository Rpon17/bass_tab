from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from fastapi import APIRouter, Depends
import redis.asyncio as redis

from app.adapters.job.job_store_redis import RedisJobStore
from app.domain.jobs_domain import MLJobStatus
from app.domain.models_domain import MLJob
from shared.dtos.main_ml_dto import MLProcessRequestDTO, MLProcessResponseDTO

# .env 로드
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

router: APIRouter = APIRouter(prefix="/v1", tags=["ml-process"])

QUEUE_NAME: str = "ml:process"


async def get_redis() -> redis.Redis:
    redis_url: str = os.getenv("REDIS_URL",)
    return redis.from_url(redis_url, decode_responses=True)


@router.post("/process", response_model=MLProcessResponseDTO)
async def submit_process(
    request: MLProcessRequestDTO,
    r: redis.Redis = Depends(get_redis),
) -> MLProcessResponseDTO:
    print("\n" + "="*30)
    print("[ml-process] submit_process entered")
    print("[ml-process] request =", request.model_dump())

    job_prefix = os.getenv("ML_JOB_KEY_PREFIX", "bass:ml:")
    store: RedisJobStore = RedisJobStore(r, key_prefix=job_prefix)


    existing: MLJob | None = await store.get(request.job_id)

    if existing is not None:
        print("[ml-process] job already exists:", request.job_id)
        return MLProcessResponseDTO(
            job_id=existing.job_id,
            song_id=existing.song_id,
            result_id=existing.result_id,
            asset_id=existing.asset_id or "",
            status=existing.status.value if isinstance(existing.status, MLJobStatus) else str(existing.status),
            path=existing.output_dir,
            error=existing.error,
        )

    print("[ml-process] job not found, creating new")

    asset_id: str = uuid.uuid4().hex
    now: str = datetime.utcnow().isoformat()

    # 💡 [핵심 수정] Path 객체가 아닌 정제된 문자열(URL 또는 로컬경로)을 저장합니다.
    job: MLJob = MLJob(
        job_id=request.job_id,
        song_id=request.song_id,
        result_id=request.result_id,
        input_wav_path=request.input_wav_path,
        output_dir=request.result_path,
        result_path=request.result_path,
        asset_id=asset_id,
        status=MLJobStatus.QUEUED,
        progress=0,
        error=None,
        norm_title=request.norm_title,
        norm_artist=request.norm_artist,
        created_at=now,
        updated_at=now,
    )

    await store.create(job, ttl_seconds=60 * 60)
    await store.enqueue(QUEUE_NAME, request.job_id)

    print("[ml-process] job enqueued successfully")

    return MLProcessResponseDTO(
        job_id=job.job_id,
        song_id=job.song_id,
        result_id=job.result_id,
        asset_id=job.asset_id or "",
        status=job.status.value if isinstance(job.status, MLJobStatus) else str(job.status),
        path=job.result_path,
        error=None,
    )