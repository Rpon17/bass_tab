# application/ports/job_store.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal

JobStatus = Literal["queued", "running", "succeeded", "failed"]


@dataclass(frozen=True)
class JobSnapshot:
    job_id: str
    status: JobStatus
    progress: float  # 0.0 ~ 1.0
    created_at_ms: int
    updated_at_ms: int
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class JobStore(ABC):
    """
        job 상태저장소
    """

    @abstractmethod
    async def create_job(
        self,
        job_id: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 60 * 30,
    ) -> None:
        """job 초기 상태 생성(queued)."""

    @abstractmethod
    async def get_status(self, job_id: str) -> Optional[JobSnapshot]:
        """job 상태 조회. 없으면 None."""

    @abstractmethod
    async def set_running(self, job_id: str) -> None:
        """queued -> running"""

    @abstractmethod
    async def set_progress(self, job_id: str, *, progress: float) -> None:
        """0.0~1.0 진행률 업데이트"""

    @abstractmethod
    async def set_succeeded(self, job_id: str, *, result: Dict[str, Any]) -> None:
        """running -> succeeded"""

    @abstractmethod
    async def set_failed(self, job_id: str, *, error: str) -> None:
        """running -> failed"""

    # ----------------
    # 락 관련
    # ----------------
    @abstractmethod
    async def acquire_lock(
        self,
        job_id: str,
        *,
        token: str,
        ttl_seconds: int = 60 * 10,
    ) -> bool:
        """성공 True / 실패 False"""

    @abstractmethod
    async def release_lock(self, job_id: str, *, token: str) -> bool:
        """token이 맞을 때만 락 해제. 성공 True / 실패 False."""

    @abstractmethod
    async def touch_ttl(self, job_id: str, *, ttl_seconds: int) -> None:
        """job TTL 연장"""
