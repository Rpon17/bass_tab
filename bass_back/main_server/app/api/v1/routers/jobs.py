# main_server/app/api/v1/routers/jobs.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.domain.jobs import JobStatus
from app.application.usecases.create_job import CreateJobUseCase
from app.application.usecases.get_job import GetJobUseCase
from app.adapters.jobs.memory_repo import InMemoryJobRepository

router = APIRouter(prefix="/jobs", tags=["jobs"])

# ⚠️ 지금은 단일 인스턴스 (나중에 DI/Redis로 교체)
_repo = InMemoryJobRepository()


def get_create_uc():
    return CreateJobUseCase(_repo)


def get_get_uc():
    return GetJobUseCase(_repo)


class CreateJobRequest(BaseModel):
    input_wav_path: str


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    input_wav_path: str | None
    result_path: str | None
    error: str | None


@router.post("", response_model=JobResponse)
def create_job(
    body: CreateJobRequest,
    uc: CreateJobUseCase = Depends(get_create_uc),
):
    job = uc.execute(input_wav_path=body.input_wav_path)
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        input_wav_path=job.input_wav_path,
        result_path=job.result_path,
        error=job.error,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    uc: GetJobUseCase = Depends(get_get_uc),
):
    try:
        job = uc.execute(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        input_wav_path=job.input_wav_path,
        result_path=job.result_path,
        error=job.error,
    )
