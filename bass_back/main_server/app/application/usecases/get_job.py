# main_server/app/application/usecases/get_job.py
from bass_back.main_server.app.application.ports.job_store import JobRepository
from app.domain.jobs import Job


class GetJobUseCase:
    def __init__(self, repo: JobRepository):
        self._repo = repo

    def execute(self, job_id: str) -> Job:
        job = self._repo.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        return job
