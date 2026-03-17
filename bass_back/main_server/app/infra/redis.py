from __future__ import annotations

import os
from redis.asyncio import Redis, from_url

_redis_client: Redis | None = None

def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:

        redis_url = os.getenv("REDIS_URL")
        
        if redis_url:
            _redis_client = from_url(redis_url, decode_responses=True)
        else:
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            db = int(os.getenv("REDIS_DB", "0"))
            _redis_client = Redis(host=host, port=port, db=db, decode_responses=True)
            
    return _redis_client

async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None