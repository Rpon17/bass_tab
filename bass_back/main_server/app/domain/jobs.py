# main_server/app/domain/job.py
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

    # ML 관련 정보
    input_wav_path: Optional[str] = None
    result_path: Optional[str] = None
    error: Optional[str] = None

    def mark_running(self):
        self.status = JobStatus.RUNNING
        self.updated_at = datetime.utcnow()

    def mark_done(self, result_path: str):
        self.status = JobStatus.DONE
        self.result_path = result_path
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error: str):
        self.status = JobStatus.FAILED
        self.error = error
        self.updated_at = datetime.utcnow()
