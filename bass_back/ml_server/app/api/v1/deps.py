from __future__ import annotations

from functools import lru_cache
from redis.asyncio import Redis

@lru_cache
def get_redis() -> Redis:
    # 네 설정에 맞게 redis url을 넣어
    return Redis.from_url("redis://localhost:6379", decode_responses=True)
