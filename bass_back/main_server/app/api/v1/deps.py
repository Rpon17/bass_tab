from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis

from app.application.ports.job_store import JobStore
from app.application.usecases.create_job import CreateJobUseCase
from app.application.usecases.get_job import GetJobUseCase
from app.adapters.jobs.job_store_redis import RedisJobStore
from app.infra.redis import get_redis


# ------------------------------------------------------------
# JobStore (Redis 구현체) 주입
# ------------------------------------------------------------
def get_job_store() -> JobStore:
    """
    JobStore 포트를 RedisJobStore로 조립한다.
    라우터 / 유스케이스는 Redis 존재를 모른다.
    """
    redis: Redis = get_redis()
    return RedisJobStore(
        redis,
        key_prefix="bass:",  # 필요 없으면 "" 로 둬도 됨
    )


# ------------------------------------------------------------
# UseCase 주입
# ------------------------------------------------------------
def get_create_uc() -> CreateJobUseCase:
    """
    Job 생성 UseCase
    """
    return CreateJobUseCase(
        job_store=get_job_store(),
    )


def get_get_uc() -> GetJobUseCase:
    """
    Job 조회 UseCase
    """
    return GetJobUseCase(
        job_store=get_job_store(),
    )
