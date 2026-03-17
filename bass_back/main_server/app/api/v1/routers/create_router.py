from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from redis.asyncio import Redis

from app.domain.jobs_domain import JobStatus
from app.domain.errors_domain import JobNotFoundError
from app.application.usecases.RequestCreateJobUseCase import RequestCreateJobUseCase
from app.application.usecases.job.get_job_usecase import GetJobUseCase
from app.application.usecases.songs.song_create_usecase import CreateSongUseCase
from app.application.usecases.songs.result_create_usecase import CreateResultUseCase
from app.application.services.text_normalize import normalize_text

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

# --- 통합 엔드포인트 ---
@router.post("", response_model=CreateResultResponse, status_code=status.HTTP_201_CREATED)
async def create_full_job(
    body: CreateResultRequest,
    redis: Redis = Depends(get_redis),
    job_uc: RequestCreateJobUseCase = Depends(get_request_create_job_uc),
    song_uc: CreateSongUseCase = Depends(get_create_song_uc),
    result_uc: CreateResultUseCase = Depends(get_create_result_uc),
) -> CreateResultResponse:
    
    # 1. Job 생성 (여기서 job_id와 result_id가 이미 세팅되어 나올 거야)
    job = await job_uc.execute(
        youtube_url=str(body.youtube_url),
        title=body.title,
        artist=body.artist,
    )
    
    # 2. Song 생성 (DB에 노래 정보 저장)
    song = await song_uc.execute(title=body.title, artist=body.artist)
    
    # 3. Result 생성 (Job과 Song을 잇는 결과물 뼈대 생성)
    # job에 들어있는 result_id를 그대로 써서 두 테이블을 동기화하는 로직!
    result = await result_uc.execute(
        result_id=job.result_id, 
        song_id=song.song_id, 
        source_url=str(body.youtube_url)
    )
    
    # 4. ML 큐 등록 (여기가 중요해 칭기야!)
    # 아까 워커에서 QUEUE_NAME = "youtube" 라고 했었지?
    # 그리고 워커는 job_id를 꺼내서 처리하도록 되어있어.
    queue_name = "youtube" # 💡 워커와 동일하게 맞춤!
    
    # 큐에는 result_id가 아니라 job_id를 넣어야 워커가 Job 정보를 조회할 수 있어.
    await redis.lpush(queue_name, job.job_id) 
    
    print(f"[API] Job queued: {job.job_id} to {queue_name}")
    
    return CreateResultResponse(
        result_id=result.result_id, 
        song_id=song.song_id
    )

# --- 조회 엔드포인트 (기존과 동일) ---
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