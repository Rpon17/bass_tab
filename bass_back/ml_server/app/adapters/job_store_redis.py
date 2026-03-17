from __future__ import annotations

from typing import Any, Dict, Optional

from redis.asyncio import Redis

from app.application.ports.jobs.job_store_port import JobStore
from app.domain.jobs_domain import MLJobStatus
from app.domain.models_domain import MLJob


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

    @staticmethod
    def _time_to_str(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        return str(v).strip()

    # ---------- serialize / deserialize ----------
    def _serialize_job(self, job: MLJob) -> Dict[str, str]:
        return {
            "job_id": (job.job_id or "").strip(),
            "result_id": (job.result_id or "").strip(),
            "song_id": (job.song_id or "").strip(),
            "input_wav_path": (job.input_wav_path or "").strip(),
            "output_dir": (job.output_dir or "").strip(),
            "result_path": (job.result_path or "").strip(),
            "norm_title": "" if job.norm_title is None else str(job.norm_title).strip(),
            "norm_artist": "" if job.norm_artist is None else str(job.norm_artist).strip(),
            "status": job.status.value,
            "progress": str(int(job.progress)),
            "error": "" if job.error is None else str(job.error).strip(),
            "created_at": self._time_to_str(job.created_at),
            "updated_at": self._time_to_str(job.updated_at),
        }

    def _deserialize_job(self, h: Dict[Any, Any]) -> MLJob:
        job_id: str = self._get_str(h, "job_id").strip()
        if not job_id:
            raise ValueError("Deserialized job has empty job_id")

        result_id: str = self._get_str(h, "result_id").strip()
        if not result_id:
            raise ValueError("Deserialized job has empty result_id")

        song_id: str = self._get_str(h, "song_id").strip()
        if not song_id:
            raise ValueError("Deserialized job has empty song_id")

        input_wav_path: str = self._get_str(h, "input_wav_path").strip()
        if not input_wav_path:
            raise ValueError("Deserialized job has empty input_wav_path")

        output_dir: str = self._get_str(h, "output_dir").strip()
        if not output_dir:
            raise ValueError("Deserialized job has empty output_dir")

        result_path: str = self._get_str(h, "result_path").strip()
        if not result_path:
            raise ValueError("Deserialized job has empty result_path")

        status_str: str = (self._get_str(h, "status") or MLJobStatus.QUEUED.value).strip()
        try:
            status: MLJobStatus = MLJobStatus(status_str)
        except ValueError:
            status = MLJobStatus.QUEUED

        progress_str: str = (self._get_str(h, "progress") or "0").strip()
        try:
            progress: int = int(progress_str)
        except ValueError:
            progress = 0

        norm_title_raw: str = self._get_str(h, "norm_title").strip()
        norm_artist_raw: str = self._get_str(h, "norm_artist").strip()
        error_raw: str = self._get_str(h, "error").strip()
        created_at_raw: str = self._get_str(h, "created_at").strip()
        updated_at_raw: str = self._get_str(h, "updated_at").strip()

        return MLJob(
            job_id=job_id,
            result_id=result_id,
            song_id=song_id,
            input_wav_path=input_wav_path,
            output_dir=output_dir,
            result_path=result_path,
            norm_title=norm_title_raw or None,
            norm_artist=norm_artist_raw or None,
            status=status,
            progress=progress,
            error=error_raw or None,
            created_at=created_at_raw,
            updated_at=updated_at_raw,
        )

    # ---------- core CRUD ----------
    async def create(self, job: MLJob, *, ttl_seconds: int = 60 * 30) -> None:
        key: str = self._job_key(job.job_id)
        if await self._r.exists(key):
            raise ValueError(f"Job already exists: {job.job_id}")

        pipe = self._r.pipeline()
        pipe.hset(key, mapping=self._serialize_job(job))
        pipe.expire(key, ttl_seconds)
        await pipe.execute()

    async def get(self, job_id: str) -> Optional[MLJob]:
        jid: str = (job_id or "").strip()
        if not jid:
            return None

        key: str = self._job_key(jid)
        print("[job-store] get key =", key)

        h: Dict[Any, Any] = await self._r.hgetall(key)
        print("[job-store] get raw hash =", h)

        if not h:
            print("[job-store] no hash found")
            return None

        try:
            job: MLJob = self._deserialize_job(h)
            print("[job-store] deserialized job =", job)
            return job
        except Exception as e:
            print(f"[job-store] deserialize failed for job_id={jid}: {e}")
            return None

    async def save(self, job: MLJob, *, ttl_seconds: Optional[int] = None) -> None:
        jid: str = (job.job_id or "").strip()
        if not jid:
            raise ValueError("Job has empty job_id (cannot save)")

        key: str = self._job_key(jid)
        if not await self._r.exists(key):
            raise ValueError(f"Job not found (cannot save): {jid}")

        pipe = self._r.pipeline()
        pipe.hset(key, mapping=self._serialize_job(job))
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

        res: Any = await self._r.eval(_UNLOCK_LUA, 1, self._lock_key(jid), tok)
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