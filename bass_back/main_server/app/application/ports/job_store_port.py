# app/application/ports/job_store.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from typing import Protocol, List

from app.domain.jobs_domain import Job
"""
    입력형태
    JobStore.create -> job(), ttl_second(ttl시간,default)
    JobStore.get -> job_id
    JobStore.save ->  job ,ttl
    JobStore.delete -> job_id
    
    JobStore.enqueue -> queue() , job_id
    JobStore.dequeue -> job_id ,ttl
    
    JobStore.acuire_lock -> job_id , token , ttl
    JobStore.release_lock -> job_id , token
    
    JobStore.touch_ttl -> job_id , ttl
    
    JobStore.add_submitted -> job_id
    JobStore.remove_submitted -> job_id
    JobStore.sample_submitted -> n(int) = communicate 워커에서 몇개 가져올지 정하는
"""
class JobStore(ABC):

    # job관련
    
    @abstractmethod
    async def create(self, job: Job, *, ttl_seconds: int = 60 * 30) -> None:
        ...

    @abstractmethod
    async def get(self, job_id: str) -> Optional[Job]:
        ...

    @abstractmethod
    async def save(self, job: Job, *, ttl_seconds: int = 60 * 30) -> None:
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
    @abstractmethod
    async def add_submitted(self, job_id: str) -> None:
        
        ...
    @abstractmethod
    async def remove_submitted(self, job_id: str) -> None:
        
        ...
    @abstractmethod
    async def sample_submitted(self, n: int) -> List[str]:
        """
        set:submitted 에서 최대 n개의 job_id를 샘플링(랜덤)해서 ml_server에 물어봄
        지금 이거 끝났어요?
        
        끝났으면 제거함
        """
        ...
