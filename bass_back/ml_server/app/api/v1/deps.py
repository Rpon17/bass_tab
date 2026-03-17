from __future__ import annotations

from functools import lru_cache
from redis.asyncio import Redis

@lru_cache
def get_redis() -> Redis:
    return Redis.from_url("redis://localhost:6379", decode_responses=True)
