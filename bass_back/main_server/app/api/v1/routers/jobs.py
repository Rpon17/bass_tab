from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl

from bass_back.main_server.app.domain.jobs_domain import Job,JobStatus
from bass_back.main_server.app.domain.errors_domain import JobNotFoundError

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

""" 
    유튜브 다운로드를 지금 당장 다 끝내는 것이 아니라
    “이 URL을 처리할 Job을 만들어서 큐에 넣고”
    “생성된 Job의 정보(job_id, status=queued 등)를 즉시 돌려주는 것”
    
    왜냐하면 여기서 등록을 하고 작업은 뒤에서 할거임 여기 JOB_ID를 가지고 작업을 하는데
    클라이언트는 이 오래걸리는 작업을기다리는동안 취소 혹은 대기화면등 여러가지 상호작용 가능하게 해야함
    계속 POST가 붙잡고 있으면 오래걸림
"""
@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    # body : HTTP 요청으로 들어온 데이터를 담는 객체
    body: CreateJobRequest,
    # uc : job을 만드는 비즈니스 로직 담당
    uc: CreateJobUseCase = Depends(get_create_uc),
):
    # 유튜브 URL로 Job 생성 (UseCase가 Job 저장 + 큐 enqueue까지 수행)
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

""" 
    응답을 받는상황
"""
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
