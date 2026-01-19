# main_server/app/application/usecases/create_job.py
import uuid
from datetime import datetime
from app.domain.jobs import Job, JobStatus
from bass_back.main_server.app.application.ports.job_store import JobRepository


class CreateJobUseCase:
    def __init__(self, repo: JobRepository):
        self._repo = repo

    def execute(self, *, input_wav_path: str) -> Job:
        job = Job(
            job_id=uuid.uuid4().hex,
            status=JobStatus.QUEUED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            input_wav_path=input_wav_path,
        )
        self._repo.save(job)
        return job
