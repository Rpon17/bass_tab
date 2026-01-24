# application/usecases/get_job.py
from dataclasses import dataclass
from bass_back.main_server.app.application.ports.job_store_port import JobStore
from bass_back.main_server.app.domain.errors_domain import JobNotFoundError
"""
    job을 조회하고 job이 있으면 get_job없으면 error작성
    책임 : job조회
"""
@dataclass(frozen=True)
class GetJobUseCase:
    job_store: JobStore

    async def execute(self, job_id: str) -> dict:
        job = await self.job_store.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job
