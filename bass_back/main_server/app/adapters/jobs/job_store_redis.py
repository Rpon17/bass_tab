# adapters/jobs/job_store_redis.py
from __future__ import annotations

import json
import time
from dataclasses import replace
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from application.ports.job_store import JobStore, JobSnapshot


def _now_ms() -> int:
    # 밀리초로 변환하는 함수
    return int(time.time() * 1000)
 



def _clamp_progress(x: float) -> float:
    # 진행률 강제하는 함수 0.0~1.0
    if x < 0.0:
        return 0.0

    if x > 1.0:
        return 1.0
    return float(x)



# 토큰을 통해 lock을 구분함
_UNLOCK_LUA =...


class RedisJobStore(JobStore):
    """
    ✅ Redis 기반 JobStore

    Key 설계:
      - job 상태:  job:{job_id} (HASH)
      - lock:     lock:job:{job_id} (STRING)

    HASH 필드:
      status, progress, created_at_ms, updated_at_ms, result_json, error, meta_json
    """

    # prefix는 string 형태지만 키워드 인자로 사용가능
    def __init__(self, redis: Redis, *, key_prefix: str = ""):
        self._r = redis # 레디스 명령어 대체
        self._p = key_prefix  # 키 역할을 해줌

    # 키의 상태를 저장함
    def _job_key(self, job_id: str) -> str:
        return f"{self._p}job:{job_id}"

    # 누가 lock을 사용중인지 리턴해줌
    def _lock_key(self, job_id: str) -> str:
        return f"{self._p}lock:job:{job_id}"

    # redis에서 읽은 hash를 jobsnapchat으로 변환함
    # redis의 문자열을 타입객체로 바꿈
    def _snap_from_hash(self, job_id: str, h: Dict[str, Any]) -> JobSnapshot:
        # 무조건 str혹은 none으로
        def _s(x: Any) -> Optional[str]:
            if x is None:
                return None
            if isinstance(x, (bytes, bytearray)):
                return x.decode("utf-8")
            return str(x)
        # sx가 비어있지 않으면 int형태로 return 해라 기본은 0
        def _i(x: Any, default: int = 0) -> int:
            sx = _s(x)
            return int(sx) if sx is not None and sx != "" else default

        #이건 위에거 float도 가능
        def _f(x: Any, default: float = 0.0) -> float:
            sx = _s(x)
            return float(sx) if sx is not None and sx != "" else default

        # status 형태나 queued 형태
        status = _s(h.get("status")) or "queued"
        
        # 진행률
        progress = _clamp_progress(_f(h.get("progress"), 0.0))
        created_at_ms = _f(h.get("created_at_ms"), 0)
        updated_at_ms = _f(h.get("updated_at_ms"), 0)

        result_json = _f(h.get("result_json"))
        meta_json = _f(h.get("meta_json"))
        error = _f(h.get("error"))

        result = json.loads(result_json) if result_json else None
        meta = json.loads(meta_json) if meta_json else None

        return JobSnapshot(
            job_id=job_id,
            status=status, 
            progress=progress,
            created_at_ms=created_at_ms,
            updated_at_ms=updated_at_ms,
            result=result,
            error=error,
            meta=meta,
        )

    # job을 생섬함
    async def create_job(
        self,
        job_id: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 60 * 30,
    ) -> None:
        now = _now_ms()
        key = self._job_key(job_id)
        
        mapping: Dict[str, Any] = {
            "status": "queued",
            "progress": "0.0",
            "created_at_ms": str(now),
            "updated_at_ms": str(now),
            "result_json": "",
            "error": "",
            "meta_json": json.dumps(meta or {}, ensure_ascii=False),
        }

        # ✅ HSET + EXPIRE를 pipeline으로 묶어서 RTT 줄임
        pipe = self._r.pipeline()
        pipe.hset(key, mapping=mapping)
        pipe.expire(key, ttl_seconds)
        await pipe.execute()

    async def get_status(self, job_id: str) -> Optional[JobSnapshot]:
        key = self._job_key(job_id)
        h = await self._r.hgetall(key)
        if not h:
            return None
        return self._snap_from_hash(job_id, h)

    async def set_running(self, job_id: str) -> None:
        key = self._job_key(job_id)
        now = _now_ms()
        # 존재하지 않으면 조용히 무시 (정책)
        await self._r.hset(key, mapping={"status": "running", "updated_at_ms": str(now)})

    async def set_progress(self, job_id: str, *, progress: float) -> None:
        key = self._job_key(job_id)
        now = _now_ms()
        p = _clamp_progress(progress)
        await self._r.hset(
            key,
            mapping={"progress": str(p), "updated_at_ms": str(now)},
        )

    async def set_succeeded(self, job_id: str, *, result: Dict[str, Any]) -> None:
        key = self._job_key(job_id)
        now = _now_ms()
        await self._r.hset(
            key,
            mapping={
                "status": "succeeded",
                "progress": "1.0",
                "result_json": json.dumps(result, ensure_ascii=False),
                "error": "",
                "updated_at_ms": str(now),
            },
        )

    async def set_failed(self, job_id: str, *, error: str) -> None:
        key = self._job_key(job_id)
        now = _now_ms()
        await self._r.hset(
            key,
            mapping={
                "status": "failed",
                "result_json": "",
                "error": error,
                "updated_at_ms": str(now),
            },
        )

    async def acquire_lock(
        self,
        job_id: str,
        *,
        token: str,
        ttl_seconds: int = 60 * 10,
    ) -> bool:
        """
        ✅ 락이 없을 때만 설정(NX) + TTL(EX)
        Redis가 원자적으로 처리해주므로 '가능여부 확인' 메서드가 필요 없음.
        """
        lk = self._lock_key(job_id)
        ok = await self._r.set(lk, token, nx=True, ex=ttl_seconds)
        return bool(ok)

    async def release_lock(self, job_id: str, *, token: str) -> bool:
        """
        ✅ 토큰이 일치할 때만 락 해제 (Lua로 원자 수행)
        """
        lk = self._lock_key(job_id)
        res = await self._r.eval(_UNLOCK_LUA, 1, lk, token)
        return int(res) == 1

    async def touch_ttl(self, job_id: str, *, ttl_seconds: int) -> None:
        key = self._job_key(job_id)
        await self._r.expire(key, ttl_seconds)
