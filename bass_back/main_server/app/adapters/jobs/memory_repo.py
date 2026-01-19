# main_server/app/adapters/jobs/memory_repo.py
from typing import Dict, Optional
from app.domain.jobs import Job
from bass_back.main_server.app.application.ports.job_store import JobRepository


class InMemoryJobRepository(JobRepository):
    def __init__(self):
        self._store: Dict[str, Job] = {}

    def save(self, job: Job) -> None:
        self._store[job.job_id] = job

    def get(self, job_id: str) -> Optional[Job]:
        return self._store.get(job_id)
