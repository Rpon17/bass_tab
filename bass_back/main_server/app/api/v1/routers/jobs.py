from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.domain.jobs_domain import JobStatus
from app.domain.errors_domain import JobNotFoundError
from app.application.usecases.RequestCreateJobUseCase import RequestCreateJobUseCase
from app.application.usecases.job.get_job_usecase import GetJobUseCase
from app.api.v1.deps import get_request_create_job_uc, get_get_job_uc

router = APIRouter(prefix="/jobs", tags=["jobs"])


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


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    uc: RequestCreateJobUseCase = Depends(get_request_create_job_uc),
) -> JobResponse:

    job = await uc.execute(
        youtube_url=str(body.youtube_url),
        title=body.title,
        artist=body.artist,
    )

    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        youtube_url=job.youtube_url,
        title=job.title,
        artist=job.artist,
        error=job.error,
    )
    
async def create_song_result_and_enqueue(
    body: CreateResultRequest,
    redis: Redis = Depends(get_redis),
    song_uc: CreateSongUseCase = Depends(get_create_song_uc),
    result_uc: CreateResultUseCase = Depends(get_create_result_uc),
) -> CreateResultResponse:
    print(f"\n[DEBUG] [results] API 호출됨. body={body.model_dump()}", flush=True)

    # 1. Song 생성
    try:
        song = await song_uc.execute(title=body.title, artist=body.artist)
        print(f"[DEBUG] [results] Song 생성 성공. song_id={song.song_id}", flush=True)
    except Exception as e:
        print(f"[ERROR] [results] Song 생성 실패: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Song 생성 실패: {str(e)}")

    # 2. Result 생성
    try:
        print("[DEBUG] [results] Result 생성 시도 중...", flush=True)
        result = await result_uc.execute(
            song_id=song.song_id,
            source_url=body.youtube_url,
        )
        print(f"[DEBUG] [results] Result 생성 성공. result_id={result.result_id}", flush=True)
    except Exception as e:
        print(f"[ERROR] [results] Result 생성 실패(데이터 저장 단계): {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Result 저장 실패: {str(e)}")
    
    # 3. Enqueue
    norm_title: str = normalize_text(body.title)
    norm_artist: str = normalize_text(body.artist)

    try:
        await _enqueue_ml_process(
            redis=redis,
            job_id=result.result_id,
            song_id=song.song_id,
            result_id=result.result_id,
            input_wav_path="",
            result_path="",
            norm_title=norm_title,
            norm_artist=norm_artist,
        )
        print("[DEBUG] [results] 모든 작업 완료, 응답 반환", flush=True)
    except Exception as exc:
        print(f"[ERROR] [results] enqueue 실패: {repr(exc)}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="result 생성은 되었지만 ML queue 등록에 실패했습니다.",
        ) from exc



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