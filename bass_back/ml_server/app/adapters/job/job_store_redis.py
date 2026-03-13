from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from app.application.ports.jobs.job_store_port import JobStore
from app.domain.jobs_domain import MLJobStatus
from app.domain.models_domain import MLJob


class RedisJobStore(JobStore):
    """
    ML 서버용 JobStore
    - MLJob CRUD + Queue + TTL
    - 디버그 로그 강화 버전
    """

    def __init__(self, redis: Redis, *, key_prefix: str = "bass:ml:") -> None:
        self._r: Redis = redis
        self._p: str = key_prefix or "bass:ml:"

    def _job_key(self, job_id: str) -> str:
        key: str = f"{self._p}job:{job_id}"
        return key

    def _queue_key(self, queue: str) -> str:
        key: str = f"{self._p}queue:{queue}"
        return key

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
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, str):
            return v.strip()
        return str(v).strip()

    def _serialize_job(self, job: MLJob) -> Dict[str, str]:
        data: Dict[str, str] = {
            "job_id": (job.job_id or "").strip(),
            "song_id": (job.song_id or "").strip(),
            "result_id": (job.result_id or "").strip(),
            "asset_id": "" if job.asset_id is None else str(job.asset_id).strip(),
            "status": job.status.value if isinstance(job.status, MLJobStatus) else str(job.status),
            "created_at": self._time_to_str(job.created_at),
            "updated_at": self._time_to_str(job.updated_at),
            "input_wav_path": (job.input_wav_path or "").strip(),
            "output_dir": (job.output_dir or "").strip(),
            "result_path": (job.result_path or "").strip(),
            "error": "" if job.error is None else str(job.error).strip(),
            "norm_title": "" if job.norm_title is None else str(job.norm_title).strip(),
            "norm_artist": "" if job.norm_artist is None else str(job.norm_artist).strip(),
            "progress": str(int(job.progress)),
        }
        return data

    def _deserialize_job(self, h: Dict[Any, Any]) -> MLJob:
        job_id: str = self._get_str(h, "job_id").strip()
        if not job_id:
            raise ValueError("Deserialized MLJob has empty job_id")

        song_id: str = self._get_str(h, "song_id").strip()
        result_id: str = self._get_str(h, "result_id").strip()

        asset_id_raw: str = self._get_str(h, "asset_id").strip()
        asset_id: str | None = asset_id_raw or None

        input_wav_path: str = self._get_str(h, "input_wav_path").strip()
        output_dir: str = self._get_str(h, "output_dir").strip()
        result_path: str = self._get_str(h, "result_path").strip()

        status_str: str = (self._get_str(h, "status") or MLJobStatus.QUEUED.value).strip()
        try:
            status: MLJobStatus = MLJobStatus(status_str)
        except ValueError:
            print(f"[ml-job-store] invalid status='{status_str}', fallback to queued")
            status = MLJobStatus.QUEUED

        progress_str: str = (self._get_str(h, "progress") or "0").strip()
        try:
            progress: int = int(progress_str)
        except ValueError:
            print(f"[ml-job-store] invalid progress='{progress_str}', fallback to 0")
            progress = 0

        created_at: str = self._get_str(h, "created_at").strip()
        updated_at: str = self._get_str(h, "updated_at").strip()
        error: str | None = self._get_str(h, "error").strip() or None
        norm_title: str | None = self._get_str(h, "norm_title").strip() or None
        norm_artist: str | None = self._get_str(h, "norm_artist").strip() or None

        return MLJob(
            job_id=job_id,
            song_id=song_id,
            result_id=result_id,
            input_wav_path=input_wav_path,
            output_dir=output_dir,
            result_path=result_path,
            asset_id=asset_id,
            norm_title=norm_title,
            norm_artist=norm_artist,
            status=status,
            progress=progress,
            error=error,
            created_at=created_at,
            updated_at=updated_at,
        )

    async def create(self, job: MLJob, *, ttl_seconds: int = 60 * 30) -> None:
        jid: str = (job.job_id or "").strip()
        if not jid:
            raise ValueError("MLJob has empty job_id (cannot create)")

        key: str = self._job_key(jid)
        print(f"[ml-job-store.create] jid={jid}")
        print(f"[ml-job-store.create] key={key}")
        print(f"[ml-job-store.create] ttl_seconds={ttl_seconds}")

        exists_before: int = int(await self._r.exists(key))
        print(f"[ml-job-store.create] exists_before={exists_before}")
        if exists_before:
            raise ValueError(f"MLJob already exists: {jid}")

        data: Dict[str, str] = self._serialize_job(job)
        print(f"[ml-job-store.create] data={data}")

        pipe = self._r.pipeline()
        pipe.hset(key, mapping=data)
        if ttl_seconds > 0:
            pipe.expire(key, ttl_seconds)
        result: list[Any] = await pipe.execute()
        print(f"[ml-job-store.create] pipeline_result={result}")

        exists_after: int = int(await self._r.exists(key))
        ttl_after: int = int(await self._r.ttl(key))
        raw_after: Dict[Any, Any] = await self._r.hgetall(key)

        print(f"[ml-job-store.create] exists_after={exists_after}")
        print(f"[ml-job-store.create] ttl_after={ttl_after}")
        print(f"[ml-job-store.create] raw_after={raw_after}")

        if exists_after == 0:
            raise RuntimeError(f"MLJob create failed: key not found right after create: {key}")

    async def get(self, job_id: str) -> Optional[MLJob]:
        jid: str = (job_id or "").strip()
        if not jid:
            print("[ml-job-store.get] empty job_id")
            return None

        key: str = self._job_key(jid)
        print(f"[ml-job-store.get] jid={jid}")
        print(f"[ml-job-store.get] key={key}")

        try:
            exists: int = int(await self._r.exists(key))
            ttl: int = int(await self._r.ttl(key))
            h: Dict[Any, Any] = await self._r.hgetall(key)

            print(f"[ml-job-store.get] exists={exists}")
            print(f"[ml-job-store.get] ttl={ttl}")
            print(f"[ml-job-store.get] raw={h}")

            if not h:
                return None

            job: MLJob = self._deserialize_job(h)
            print(f"[ml-job-store.get] deserialized={job}")
            return job

        except Exception as e:
            print(f"[ml-job-store.get] failed for jid={jid}: {type(e).__name__}: {e}")
            raise

    async def save(self, job: MLJob, *, ttl_seconds: int = 60 * 30) -> None:
        jid: str = (job.job_id or "").strip()
        if not jid:
            raise ValueError("MLJob has empty job_id (cannot save)")

        key: str = self._job_key(jid)
        print(f"[ml-job-store.save] jid={jid}")
        print(f"[ml-job-store.save] key={key}")
        print(f"[ml-job-store.save] ttl_seconds={ttl_seconds}")

        exists_before: int = int(await self._r.exists(key))
        print(f"[ml-job-store.save] exists_before={exists_before}")
        if not exists_before:
            raise ValueError(f"MLJob not found (cannot save): {jid}")

        data: Dict[str, str] = self._serialize_job(job)
        print(f"[ml-job-store.save] data={data}")

        pipe = self._r.pipeline()
        pipe.hset(key, mapping=data)
        if ttl_seconds > 0:
            pipe.expire(key, ttl_seconds)
        result: list[Any] = await pipe.execute()
        print(f"[ml-job-store.save] pipeline_result={result}")

        exists_after: int = int(await self._r.exists(key))
        ttl_after: int = int(await self._r.ttl(key))
        print(f"[ml-job-store.save] exists_after={exists_after}")
        print(f"[ml-job-store.save] ttl_after={ttl_after}")

    async def delete(self, job_id: str) -> None:
        jid: str = (job_id or "").strip()
        if not jid:
            print("[ml-job-store.delete] empty job_id")
            return

        key: str = self._job_key(jid)
        deleted: int = int(await self._r.delete(key))
        print(f"[ml-job-store.delete] jid={jid} key={key} deleted={deleted}")

    async def enqueue(self, queue: str, job_id: str) -> None:
        q: str = (queue or "").strip()
        jid: str = (job_id or "").strip()

        if not q:
            raise ValueError("enqueue() got empty queue")
        if not jid:
            raise ValueError("enqueue() got empty job_id")

        key: str = self._queue_key(q)
        length_after: int = int(await self._r.lpush(key, jid))

        print(f"[ml-job-store.enqueue] queue={q}")
        print(f"[ml-job-store.enqueue] key={key}")
        print(f"[ml-job-store.enqueue] jid={jid}")
        print(f"[ml-job-store.enqueue] length_after={length_after}")

    async def dequeue(self, queue: str, *, timeout_seconds: int = 5) -> Optional[str]:
        q: str = (queue or "").strip()
        if not q:
            print("[ml-job-store.dequeue] empty queue")
            return None

        key: str = self._queue_key(q)
        print(f"[ml-job-store.dequeue] queue={q}")
        print(f"[ml-job-store.dequeue] key={key}")
        print(f"[ml-job-store.dequeue] timeout_seconds={timeout_seconds}")

        item: Any = await self._r.brpop(key, timeout=timeout_seconds)
        print(f"[ml-job-store.dequeue] raw_item={item}")

        if not item:
            return None

        _, raw = item
        jid: str = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
        jid = jid.strip()

        print(f"[ml-job-store.dequeue] jid={jid}")
        return jid or None

    async def touch_ttl(self, job_id: str, *, ttl_seconds: int) -> None:
        jid: str = (job_id or "").strip()
        if not jid:
            print("[ml-job-store.touch_ttl] empty job_id")
            return

        key: str = self._job_key(jid)
        result: bool = bool(await self._r.expire(key, ttl_seconds))
        ttl_after: int = int(await self._r.ttl(key))

        print(f"[ml-job-store.touch_ttl] jid={jid}")
        print(f"[ml-job-store.touch_ttl] key={key}")
        print(f"[ml-job-store.touch_ttl] expire_result={result}")
        print(f"[ml-job-store.touch_ttl] ttl_after={ttl_after}")