from __future__ import annotations

import os
from functools import lru_cache

from redis.asyncio import Redis

""" 
    이건 실제 클라이언트 객체를 만듬
"""
@lru_cache
# 첫 호출시 객체를 생성함
def get_redis() -> Redis:
    # 환경변수 redis_host값 읽기
    host = os.getenv("REDIS_HOST", "localhost")
    # 환경변수 redis_port값 읽기
    port = int(os.getenv("REDIS_PORT", "6379"))
    # 환경변수 redis_db값 읽기
    db = int(os.getenv("REDIS_DB", "0"))

    # 객체를 생성함 host와 port와 db다 위에 고정한대로 그리고 이건 str로 받음
    return Redis(host=host, port=port, db=db, decode_responses=True)

# 애플리케이션 종료시 닫음
async def close_redis() -> None:
    # 캐시된 Redis 클라이언트를 가져옴
    r = get_redis()
    # 닫아버림
    await r.close()
