# app/application/ports/job_store.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

from bass_back.main_server.app.domain.jobs_domain import Job

class JobStore(ABC):

    @abstractmethod
    async def create(self, job: Job, *, ttl_seconds: int = 60 * 30) -> None:
        ...

    @abstractmethod
    async def get(self, job_id: str) -> Optional[Job]:
        ...

    @abstractmethod
    async def save(self, job: Job, *, ttl_seconds: Optional[int] = None) -> None:
        ...

    @abstractmethod
    async def delete(self, job_id: str) -> None:
        ...
        
    @abstractmethod
    async def enqueue(self, queue: str, job_id: str) -> None:
        ...
        
    @abstractmethod
    async def acquire_lock(
        self,
        job_id: str,
        *,
        token: str,
        ttl_seconds: int = 60 * 10,
    ) -> bool:
        ...

    @abstractmethod
    async def release_lock(self, job_id: str, *, token: str) -> bool:
        ...
        
    @abstractmethod
    async def touch_ttl(self, job_id: str, *, ttl_seconds: int) -> None:
        ...
        
    