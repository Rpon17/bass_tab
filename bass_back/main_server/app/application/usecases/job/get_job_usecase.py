# application/usecases/get_job.py
from dataclasses import dataclass

from app.application.ports.job_store_port import JobStore
from app.domain.errors_domain import JobNotFoundError
from app.domain.jobs_domain import Job
"""
    input
        클래스 
            !adapter의 클래스명
        
        execute 메소드
            !job_id
        
"""
@dataclass(frozen=True)
class GetJobUseCase:
    job_store: JobStore

    async def execute(self, job_id: str) -> Job:
        job = await self.job_store.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

