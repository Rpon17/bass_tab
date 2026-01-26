from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis

from bass_back.main_server.app.application.ports.job_store_port import JobStore
from bass_back.main_server.app.application.usecases.create_job_usecase import CreateJobUseCase
from bass_back.main_server.app.application.usecases.get_job_usecase import GetJobUseCase
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
    # 바로 이 코드에서 get_redis 객체를 생성함
    redis: Redis = get_redis()
    return RedisJobStore(
        redis,
        key_prefix="bass:",  # 필요 없으면 "" 로 둬도 됨
    )


# ------------------------------------------------------------
# 유스케이스에도 실제 클라이언트 객체를 넣음
# ------------------------------------------------------------
def get_create_uc() -> CreateJobUseCase:
    return CreateJobUseCase(
        job_store=get_job_store(),
    )


def get_get_uc() -> GetJobUseCase:
    return GetJobUseCase(
        job_store=get_job_store(),
    )
