from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.redis import get_redis
from app.application.usecases.songs.song_create_usecase import CreateSongUseCase
from app.application.usecases.songs.result_create_usecase import CreateResultUseCase
from app.api.v1.dto.results_dto import CreateResultRequest, CreateResultResponse
from app.api.v1.deps import get_create_song_uc, get_create_result_uc


router = APIRouter(tags=["ml-process"])
print("[ml-process] ROUTER FILE LOADED")


class MLProcessRequest(BaseModel):
    job_id: str = Field(..., description="Job 식별자")
    song_id: str = Field(..., description="곡 식별자")
    result_id: str = Field(..., description="결과 식별자")
    input_wav_path: str = Field(..., description="ML 입력 wav 파일 경로")
    result_path: str = Field(..., description="결과 저장 루트 경로")
    norm_title: str | None = None
    norm_artist: str | None = None


class MLProcessResponse(BaseModel):
    ok: bool
    status: Literal["queued"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ml_queue_key() -> str:
    return "ml:queue:process"


def _ml_status_key(job_id: str) -> str:
    return f"ml:status:{job_id}"


@router.post(
    "/v1/process",
    response_model=MLProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_ml_process(
    body: MLProcessRequest,
    redis: Redis = Depends(get_redis),
) -> MLProcessResponse:
    print("[ml-process] entered")
    print("[ml-process] body =", body.model_dump())
    print("[ml-process] redis =", redis)
    print("[ml-process] redis_type =", type(redis))

    job_id: str = body.job_id

    print("[ml-process] before hset")
    await redis.hset(
        _ml_status_key(job_id),
        mapping={
            "status": "queued",
            "song_id": body.song_id,
            "result_id": body.result_id,
            "input_wav_path": body.input_wav_path,
            "result_path": body.result_path,
            "norm_title": "" if body.norm_title is None else body.norm_title,
            "norm_artist": "" if body.norm_artist is None else body.norm_artist,
            "updated_at": _utcnow_iso(),
        },
    )
    print("[ml-process] after hset")

    print("[ml-process] before lpush")
    await redis.lpush(_ml_queue_key(), job_id)
    print("[ml-process] after lpush")

    return MLProcessResponse(ok=True, status="queued")


@router.post(
    "/results",
    response_model=CreateResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_song_and_result(
    body: CreateResultRequest,
    song_uc: CreateSongUseCase = Depends(get_create_song_uc),
    result_uc: CreateResultUseCase = Depends(get_create_result_uc),
) -> CreateResultResponse:
    song = await song_uc.execute(
        title=body.title,
        artist=body.artist,
    )

    result = await result_uc.execute(
        song_id=song.song_id,
        source_url=body.youtube_url,
    )

    return CreateResultResponse(
        result_id=result.result_id,
        song_id=result.song_id,
    )