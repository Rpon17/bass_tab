from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from redis.asyncio import Redis

# 도메인 및 유스케이스
from app.domain.jobs_domain import JobStatus
from app.domain.errors_domain import JobNotFoundError
from app.application.usecases.RequestCreateJobUseCase import RequestCreateJobUseCase
from app.application.usecases.job.get_job_usecase import GetJobUseCase
from app.application.usecases.songs.song_create_usecase import CreateSongUseCase
from app.application.usecases.songs.result_create_usecase import CreateResultUseCase
from app.application.services.text_normalize import normalize_text

# 의존성 및 DTO
from app.infra.redis import get_redis
from app.api.v1.deps import (
    get_request_create_job_uc, 
    get_get_job_uc, 
    get_create_song_uc, 
    get_create_result_uc
)
from app.api.v1.dto.results_dto import CreateResultRequest, CreateResultResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])

# --- 모델 ---
class CreateJobRequest(BaseModel):
    youtube_url: HttpUrl
    title: str
    artist: str

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    youtube_url: str | None = None
    title: str | None = None
    artist: str | None = None
    error: str | None = None

# --- 통합 엔드포인트: Job 생성 + Song/Result 생성 + ML 큐 등록 ---
@router.post("", response_model=CreateResultResponse, status_code=status.HTTP_201_CREATED)
async def create_full_job(
    body: CreateResultRequest,
    redis: Redis = Depends(get_redis),
    job_uc: RequestCreateJobUseCase = Depends(get_request_create_job_uc),
    song_uc: CreateSongUseCase = Depends(get_create_song_uc),
    result_uc: CreateResultUseCase = Depends(get_create_result_uc),
) -> CreateResultResponse:
    
    # 1. 기존 Job 생성 로직 실행
    job = await job_uc.execute(
        youtube_url=str(body.youtube_url),
        title=body.title,
        artist=body.artist,
    )
    
    # 2. Song 생성
    song = await song_uc.execute(title=body.title, artist=body.artist)
    
    # 3. Result 생성
    result = await result_uc.execute(result_id=job.result_id,song_id=song.song_id, source_url=body.youtube_url)
    
    # 4. ML 큐 등록
    norm_title = normalize_text(body.title)
    norm_artist = normalize_text(body.artist)
    
    # ML 프로세스 큐잉
    await redis.lpush("ml:queue:process", result.result_id)
    
    return CreateResultResponse(
        result_id=result.result_id, 
        song_id=song.song_id
    )

# --- 조회 엔드포인트 ---
@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    uc: GetJobUseCase = Depends(get_get_job_uc),
) -> JobResponse:
    try:
        job = await uc.execute(job_id=job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        youtube_url=job.youtube_url,
        title=job.title,
        artist=job.artist,
        error=job.error,
    )