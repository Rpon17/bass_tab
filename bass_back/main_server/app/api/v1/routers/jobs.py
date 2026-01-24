from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl

from bass_back.main_server.app.domain.jobs_domain import JobStatus
from bass_back.main_server.app.application.usecases.create_job_usecase import CreateJobUseCase
from bass_back.main_server.app.application.usecases.get_job_usecase import GetJobUseCase
from app.api.v1.deps import get_create_uc, get_get_uc  # Redis 기반으로 조립된 Depends

router = APIRouter(prefix="/jobs", tags=["jobs"])


"""
라우터가 실제로 하는 일
1) HTTP 요청을 DTO로 받음
2) UseCase 호출
3) Domain 객체 → Response DTO로 변환
"""


class CreateJobRequest(BaseModel):
    youtube_url: HttpUrl  # 문자열보다 안전하게 검증됨


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    youtube_url: str | None = None
    input_wav_path: str | None = None
    result_path: str | None = None
    error: str | None = None


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    # body : HTTP 요청으로 들어온 데이터를 담는 객체
    body: CreateJobRequest,
    # uc : job을 만드는 비즈니스 로직 담당
    uc: CreateJobUseCase = Depends(get_create_uc),
):
    # ✅ 유튜브 URL로 Job 생성 (UseCase가 Job 저장 + 큐 enqueue까지 수행)
    job = await uc.execute(youtube_url=str(body.youtube_url))

    # ✅ Domain Job → API Response DTO
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        youtube_url=job.youtube_url,
        input_wav_path=job.input_wav_path,
        result_path=job.result_path,
        error=job.error,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    uc: GetJobUseCase = Depends(get_get_uc),
):
    job = await uc.execute(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        youtube_url=job.youtube_url,
        input_wav_path=job.input_wav_path,
        result_path=job.result_path,
        error=job.error,
    )
