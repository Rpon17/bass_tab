from __future__ import annotations

import os
from redis.asyncio import Redis
from dotenv import load_dotenv

load_dotenv()

def get_redis() -> Redis:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    return Redis.from_url(redis_url, decode_responses=True)