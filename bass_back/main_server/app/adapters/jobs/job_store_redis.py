# main_server/app/adapters/jobs/job_store_redis.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis

from app.application.ports.job_store_port import JobStore
from app.domain.jobs_domain import Job, JobStatus


_UNLOCK_LUA: str = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


class RedisJobStore(JobStore):
    def __init__(self, redis: Redis, *, key_prefix: str = "bass:") -> None:
        self._r: Redis = redis
        self._p: str = key_prefix or "bass:"

    # ---------- key builders ----------
    def _job_key(self, job_id: str) -> str:
        return f"{self._p}job:{job_id}"

    def _lock_key(self, job_id: str) -> str:
        return f"{self._p}lock:job:{job_id}"

    def _queue_key(self, queue: str) -> str:
        return f"{self._p}queue:{queue}"

    def _submitted_key(self) -> str:
        return f"{self._p}ml:submitted"

    # ---------- datetime helpers ----------
    @staticmethod
    def _dt_to_str(dt: datetime) -> str:
        return dt.isoformat()

    @staticmethod
    def _str_to_dt(s: str) -> datetime:
        if not s:
            return datetime.utcnow()
        return datetime.fromisoformat(s)

    # ---------- decode helpers ----------
    @staticmethod
    def _to_str(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (bytes, bytearray)):
            return v.decode()
        return str(v)

    @classmethod
    def _get_str(cls, h: Dict[Any, Any], key: str) -> str:
        v: Any = h.get(key)
        if v is None:
            v = h.get(key.encode())
        return cls._to_str(v)

    # ---------- serialize / deserialize ----------
    def _serialize_job(self, job: Job) -> Dict[str, str]:
        """
        Redis HASH에는 None을 넣을 수 없으므로 Optional 값은 ""로 저장한다.
        """
        return {
            "job_id": (job.job_id or "").strip(),
            "song_id": (job.song_id or "").strip(),
            "result_id": (job.result_id or "").strip(),
            "status": job.status.value,
            "created_at": self._dt_to_str(job.created_at),
            "updated_at": self._dt_to_str(job.updated_at),
            "youtube_url": (job.youtube_url or "").strip(),
            "title": (job.title or "").strip(),
            "artist": (job.artist or "").strip(),
            "error": (job.error or "").strip(),
        }

    def _deserialize_job(self, h: Dict[Any, Any]) -> Job:
        """
        Redis hgetall()은 dict[bytes, bytes]일 수 있으므로
        str / bytes key 모두 안전하게 처리한다.
        """
        job_id: str = self._get_str(h, "job_id").strip()
        if not job_id:
            raise ValueError("Deserialized job has empty job_id (Redis data corrupted)")

        song_id: str = self._get_str(h, "song_id").strip()
        if not song_id:
            raise ValueError("Deserialized job has empty song_id (Redis data corrupted)")

        # ✅ QUEUED 단계에서는 result_id가 없을 수 있음
        result_id_str: str = self._get_str(h, "result_id").strip()
        result_id: Optional[str] = result_id_str if result_id_str else None

        status_str: str = (self._get_str(h, "status") or JobStatus.QUEUED.value).strip()
        try:
            status: JobStatus = JobStatus(status_str)
        except ValueError:
            status = JobStatus.QUEUED

        return Job(
            job_id=job_id,
            song_id=song_id,
            result_id=result_id,
            status=status,
            created_at=self._str_to_dt(self._get_str(h, "created_at")),
            updated_at=self._str_to_dt(self._get_str(h, "updated_at")),
            youtube_url=(self._get_str(h, "youtube_url").strip() or None),
            title=(self._get_str(h, "title").strip() or None),
            artist=(self._get_str(h, "artist").strip() or None),
            error=(self._get_str(h, "error").strip() or None),
        )

    # ---------- core CRUD ----------
    async def create(self, job: Job, *, ttl_seconds: int = 60 * 30) -> None:
        key: str = self._job_key(job.job_id)
        if await self._r.exists(key):
            raise ValueError(f"Job already exists: {job.job_id}")

        data: Dict[str, str] = self._serialize_job(job)

        pipe = self._r.pipeline()
        pipe.hset(key, mapping=data)
        pipe.expire(key, ttl_seconds)
        await pipe.execute()

    async def get(self, job_id: str) -> Optional[Job]:
        jid: str = (job_id or "").strip()
        if not jid:
            return None

        h: Dict[Any, Any] = await self._r.hgetall(self._job_key(jid))
        if not h:
            return None
        return self._deserialize_job(h)

    async def save(self, job: Job, *, ttl_seconds: Optional[int] = None) -> None:
        jid: str = (job.job_id or "").strip()
        if not jid:
            raise ValueError("Job has empty job_id (cannot save)")

        key: str = self._job_key(jid)
        if not await self._r.exists(key):
            raise ValueError(f"Job not found (cannot save): {jid}")

        data: Dict[str, str] = self._serialize_job(job)

        pipe = self._r.pipeline()
        pipe.hset(key, mapping=data)
        if ttl_seconds is not None:
            pipe.expire(key, ttl_seconds)
        await pipe.execute()

    async def delete(self, job_id: str) -> None:
        jid: str = (job_id or "").strip()
        if jid:
            await self._r.delete(self._job_key(jid))

    # ---------- queue ----------
    async def enqueue(self, queue: str, job_id: str) -> None:
        q: str = (queue or "").strip()
        jid: str = (job_id or "").strip()
        if not q:
            raise ValueError("enqueue() got empty queue")
        if not jid:
            raise ValueError("enqueue() got empty job_id")
        await self._r.lpush(self._queue_key(q), jid)

    async def dequeue(self, queue: str, *, timeout_seconds: int = 5) -> Optional[str]:
        q: str = (queue or "").strip()
        if not q:
            return None

        item = await self._r.brpop(self._queue_key(q), timeout=timeout_seconds)
        if not item:
            return None

        _, raw = item
        jid: str = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
        jid = jid.strip()
        return jid or None

    # ---------- lock ----------
    async def acquire_lock(self, job_id: str, *, token: str, ttl_seconds: int = 600) -> bool:
        jid: str = (job_id or "").strip()
        tok: str = (token or "").strip()
        if not jid or not tok:
            return False
        return bool(await self._r.set(self._lock_key(jid), tok, nx=True, ex=ttl_seconds))

    async def release_lock(self, job_id: str, *, token: str) -> bool:
        jid: str = (job_id or "").strip()
        tok: str = (token or "").strip()
        if not jid or not tok:
            return False
        res = await self._r.eval(_UNLOCK_LUA, 1, self._lock_key(jid), tok)
        return int(res) == 1

    async def touch_ttl(self, job_id: str, *, ttl_seconds: int) -> None:
        jid: str = (job_id or "").strip()
        if jid:
            await self._r.expire(self._job_key(jid), ttl_seconds)

    # ---------- submitted ----------
    async def add_submitted(self, job_id: str) -> None:
        jid: str = (job_id or "").strip()
        if not jid:
            return
        await self._r.sadd(self._submitted_key(), jid)

    async def remove_submitted(self, job_id: str) -> None:
        jid: str = (job_id or "").strip()
        if not jid:
            return
        await self._r.srem(self._submitted_key(), jid)

    async def sample_submitted(self, n: int = 10) -> List[str]:
        if n <= 0:
            return []

        raw = await self._r.srandmember(self._submitted_key(), n)
        if not raw:
            return []

        if isinstance(raw, (bytes, bytearray, str)):
            raw = [raw]

        out: List[str] = []
        for x in raw:
            if isinstance(x, (bytes, bytearray)):
                out.append(x.decode())
            else:
                out.append(str(x))
        return out
