# app/application/ports/job_store.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from typing import Protocol, List

from bass_back.main_server.app.domain.jobs_domain import Job

class JobStore(ABC):

    # job관련
    
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
    async def dequeue(self, queue: str, *, timeout_seconds: int = 5) -> Optional[str]:
        ...

    # lock 관련
    
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

    #submitt 관련
    
    async def add_submitted(self, job_id: str) -> None:
        ...

    async def remove_submitted(self, job_id: str) -> None:
        ...

    async def sample_submitted(self, n: int) -> List[str]:
        """
        set:submitted 에서 최대 n개의 job_id를 샘플링(랜덤)해서 ml_server에 물어봄
        지금 이거 끝났어요?
        
        끝났으면 제거함
        """
        ...
