# app/application/ports/job_store.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from typing import Protocol, List

from app.domain.jobs_domain import MLJobStatus
from app.domain.models_domain import MLJob
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
    async def create(self, job: MLJob, *, ttl_seconds: int = 60 * 30) -> None:
        ...

    @abstractmethod
    async def get(self, job_id: str) -> Optional[MLJob]:
        ...

    @abstractmethod
    async def save(self, job: MLJob, *, ttl_seconds: int = 60 * 30) -> None:
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

    @abstractmethod
    async def touch_ttl(self, job_id: str, *, ttl_seconds: int) -> None:
        ...
