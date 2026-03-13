from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    song_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime

    result_id: str | None
    asset_id: str | None
    path: str | None = None

    youtube_url: Optional[str] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        song_id: str,
        result_id: str,
        youtube_url: Optional[str] = None,
        title: Optional[str] = None,
        artist: Optional[str] = None,
    ) -> "Job":
        now = _utc_now()

        return cls(
            job_id=job_id,
            song_id=song_id,
            result_id=result_id,
            asset_id=None,
            path=None,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            youtube_url=youtube_url,
            title=title,
            artist=artist,
            error=None,
        )

    def mark_submitted(self) -> None:
        if self.status != JobStatus.QUEUED:
            raise ValueError("Job must be QUEUED to start submitted")

        self.status = JobStatus.SUBMITTED
        self.updated_at = _utc_now()

    def mark_done(self, *, path: str) -> None:
        if self.status != JobStatus.SUBMITTED:
            raise ValueError("Job must be SUBMITTED to be done")

        self.status = JobStatus.DONE
        self.path = path
        self.updated_at = _utc_now()

    def mark_failed(self, *, error: str) -> None:
        self.status = JobStatus.FAILED
        self.error = error
        self.updated_at = _utc_now()