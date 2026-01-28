from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from typing import Literal

from bass_back.main_server.app.domain.jobs_domain import JobStatus, SourceMode, ResultMode
from bass_back.main_server.app.domain.errors_domain import JobNotFoundError
from bass_back.main_server.app.application.usecases.create_job_usecase import CreateJobUseCase
from bass_back.main_server.app.application.usecases.get_job_usecase import GetJobUseCase
from app.api.v1.deps import get_create_uc, get_get_uc

router = APIRouter(prefix="/jobs", tags=["jobs"])

# # DTO매핑을 위함
SOURCE_MODE_MAP: dict[str, SourceMode] = {
    "원곡": SourceMode.ORIGINAL,
    "근음": SourceMode.ROOT,
}
RESULT_MODE_MAP: dict[str, ResultMode] = {
    "전부": ResultMode.FULL,
    "음원": ResultMode.SEPARATE, 
}


class CreateJobRequest(BaseModel):
    youtube_url: HttpUrl
    source_mode: Literal["원곡", "근음"] = "원곡"
    result_mode: Literal["전부", "음원"] = "전부"


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    youtube_url: str | None = None
    input_wav_path: str | None = None
    result_path: str | None = None
    error: str | None = None

# 이 작업이 들어오면 job을 생성한다
# 그러면 자동으로 enqueue되다가 노는 워커가 일을 가져가서 한다
@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    uc: CreateJobUseCase = Depends(get_create_uc),
):
    source_mode = SOURCE_MODE_MAP[body.source_mode]
    result_mode = RESULT_MODE_MAP[body.result_mode]

    # usecase에 보낼 정보들 이걸 기반으로 job을 만든다
    job = await uc.execute(
        youtube_url=str(body.youtube_url),
        source_mode=source_mode,
        result_mode=result_mode,
    )

    # 도메인 객체를 그대로 밖으내 내보내는게 아닌 http응답 전용으로 포장함
    # 이걸 그대로 내보내면 한번 job_id에 진짜 job_id값을 저장해서 포장해서 보냄
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
    try:
        job = await uc.execute(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        youtube_url=job.youtube_url,
        input_wav_path=job.input_wav_path,
        result_path=job.result_path,
        error=job.error,
    )
