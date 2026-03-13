from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping ,Optional

from shared.dtos.main_ml_dto import MLProcessResponseDTO
from app.domain.jobs_domain import MLJobStatus
from app.domain.errors_domain import InvalidStateTransition
from app.services.time_utils import utc_now_iso


@dataclass
class MLJob:
    """
    job_id: ML 서버 내부 작업 추적/큐 처리 식별자 (worker 단위)
    result_id: 산출물 번들 식별자 (저장 구조 기준)
    song_id: 곡 식별자
    """
    job_id: str
    result_id: str
    song_id: str

    input_wav_path: str
    output_dir: str 
    result_path: str
    
    asset_id: Optional[str] = None
    norm_title: str = None
    norm_artist: str = None


    status: MLJobStatus = MLJobStatus.QUEUED
    progress: int = 0
    error: str | None = None

    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def _touch(self) -> None:
        self.updated_at = utc_now_iso()

    def mark_running(self) -> None:
        if self.status != MLJobStatus.QUEUED:
            raise InvalidStateTransition("Job must be QUEUED to be running")
        self.status = MLJobStatus.RUNNING
        self.error = None
        self.progress = max(self.progress, 1)
        self._touch()

    def set_progress(self, *, progress: int) -> None:
        if self.status != MLJobStatus.RUNNING:
            raise InvalidStateTransition(f"{self.status} -> progress not allowed")
        clamped: int = max(0, min(100, int(progress)))
        self.progress = clamped
        self._touch()

    def mark_done(self) -> None:
        if self.status != MLJobStatus.RUNNING:
            raise InvalidStateTransition(f"{self.status} -> done not allowed")
        self.status = MLJobStatus.DONE
        self.progress = 100
        self.error = None
        self._touch()

    def mark_failed(self, *, error: str) -> None:
        if self.status not in (MLJobStatus.QUEUED, MLJobStatus.RUNNING):
            raise InvalidStateTransition(f"{self.status} -> failed not allowed")
        self.status = MLJobStatus.FAILED
        self.error = error
        self.progress = min(self.progress, 99)
        self._touch()

    def to_public_payload(self) -> MLProcessResponseDTO:
        return MLProcessResponseDTO(
            job_id=self.job_id,
            song_id=self.song_id,
            result_id=self.result_id,
            asset_id=self.asset_id,
            status=self.status.value,
            path=self.result_path,
            error=self.error,
        )