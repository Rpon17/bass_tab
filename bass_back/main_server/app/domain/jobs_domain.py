# main_server/app/domain/jobs.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    
    youtube_url: Optional[str] = None
    input_wav_path: Optional[str] = None
    result_path: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        youtube_url: Optional[str] = None,
        input_wav_path: Optional[str] = None,
        ) -> "Job":
        now = datetime.utcnow()
        return cls(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            youtube_url=youtube_url,
            input_wav_path=input_wav_path,
        )

    def mark_running(self) -> None:
        if self.status != JobStatus.QUEUED:
            raise ValueError("Job must be QUEUED to start running")

        self.status = JobStatus.RUNNING
        self.updated_at = datetime.utcnow()

    def mark_done(self, *, result_path: str) -> None:
        if self.status != JobStatus.RUNNING:
            raise ValueError("Job must be RUNNING to be done")

        self.status = JobStatus.DONE
        self.result_path = result_path
        self.updated_at = datetime.utcnow()

    def mark_failed(self, *, error: str) -> None:
        self.status = JobStatus.FAILED
        self.error = error
        self.updated_at = datetime.utcnow()
