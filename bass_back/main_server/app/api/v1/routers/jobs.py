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
    norm_title: str | None = None
    norm_artist: str | None = None

    # ✅ 최신 설계: Job에는 output_dir/result_path 없음 (워커 submit 시 result_path 계산)
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


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    uc: GetJobUseCase = Depends(get_get_job_uc),
) -> JobResponse:
    try:
        job = await uc.execute(job_id)
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
