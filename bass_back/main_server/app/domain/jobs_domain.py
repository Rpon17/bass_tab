# main_server/app/domain/jobs.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime


class JobStatus(str, Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    DONE = "done"
    FAILED = "failed"

class SourceMode(str, Enum):
    ORIGINAL = "original"  
    ROOT = "root"  

class ResultMode(str, Enum):
    SEPARATE = "separate"  
    FULL = "full"  
    
@dataclass
class Job:
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    
    youtube_url: Optional[str] = None
    source_mode : SourceMode = SourceMode.ORIGINAL
    result_mode : ResultMode = ResultMode.FULL
    input_wav_path: Optional[str] = None
    result_path: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        youtube_url: Optional[str] = None,
        source_mode : SourceMode = SourceMode.ORIGINAL,
        result_mode : ResultMode = ResultMode.FULL,
        input_wav_path: Optional[str] = None,
        ) -> "Job":
        now = datetime.utcnow()
        return cls(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            youtube_url=youtube_url,
            source_mode = source_mode,
            result_mode = result_mode,
            input_wav_path=input_wav_path,
        )

    def mark_submitted(self) -> None:
        if self.status != JobStatus.QUEUED:
            raise ValueError("Job must be QUEUED to start submitted")

        self.status = JobStatus.SUBMITTED
        self.updated_at = datetime.utcnow()

    def mark_done(self, *, result_path: str) -> None:
        if self.status != JobStatus.SUBMITTED:
            raise ValueError("Job must be SUBMITTED to be done")

        self.status = JobStatus.DONE
        self.result_path = result_path
        self.updated_at = datetime.utcnow()

    def mark_failed(self, *, error: str) -> None:
        self.status = JobStatus.FAILED
        self.error = error
        self.updated_at = datetime.utcnow()
