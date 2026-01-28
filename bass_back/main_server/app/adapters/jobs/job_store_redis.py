# adapters/jobs/job_store_redis.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, List

from redis.asyncio import Redis

from bass_back.main_server.app.application.ports.job_store_port import JobStore
from bass_back.main_server.app.domain.jobs_domain import Job, JobStatus, SourceMode ,ResultMode
# ------------------------------------------------------------
# Redis 락 해제: token이 맞을 때만 삭제 (원자적)
# ------------------------------------------------------------
_UNLOCK_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""



class RedisJobStore(JobStore):
    """
    Redis 기반 JobStore(Repository) 구현체.

    Key 설계:
      - Job 데이터:  {prefix}job:{job_id}        (HASH)
      - Job 락:      {prefix}lock:job:{job_id}   (STRING)

    HASH 필드:
      job_id, status, created_at, updated_at, input_wav_path, result_path, error
    """

    def __init__(self, redis: Redis, *, key_prefix: str = ""):
        self._r = redis
        self._p = key_prefix or ""

    def _job_key(self, job_id: str) -> str:
        return f"{self._p}job:{job_id}"

    def _lock_key(self, job_id: str) -> str:
        return f"{self._p}lock:job:{job_id}"

    # -----------------------------
    """ 
        reids는 객체를 모른다 job_id랑 status이런건 redis에서 모른다
        그래서 "job_id" "status" 이런식으로 redis에 넣어준다
    """
    # -----------------------------
    
    # none 이라면 "" 로 빈 문자열로 아니라면 string으로
    # 사실 관례적으로 값이 없으면 ""로 통일한다
    @staticmethod
    def _to_str(v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    # datetime을  역 직렬화 함
    @staticmethod
    def _dt_to_str(dt: datetime) -> str:
        # UTC 기준으로 저장하는 게 일반적(너는 create에서 utcnow 사용 중)
        return dt.isoformat()

    # datetime을 직렬화 함
    @staticmethod
    def _str_to_dt(s: str) -> datetime:
        if not s:
            return datetime.utcnow()
        return datetime.fromisoformat(s)

    # job을 직렬화하는 과정
    """
        job_id : 여기에 들어온 job의 dict는 다 직렬화 된다
        job_id라는 문자열에 job_id값을 넣고 status에 값을 넣는다 이런식으로 값을
        “Redis의 job:{job_id} 해시 안에
        job_id라는 필드가 있고,
        그 필드의 값이 실제 job_id 문자열이다.”
        
        Key: "job:abc"       ← Redis의 key
        Type: Hash
        Fields:
            job_id          -> "abc"
            status          -> "QUEUED"
            created_at      -> "2026-01-23T15:42:10"
            updated_at      -> "2026-01-23T15:42:10"
            input_wav_path  -> "/data/jobs/abc/input.wav"
            result_path     -> ""
            error           -> ""
        
        이런식으로 객체를 만들고 그곳에 데이터를 넣음
    """
    def _serialize_job(self, job: Job) -> Dict[str, str]:
        return {
            "job_id": job.job_id,
            "status": job.status.value if isinstance(job.status, JobStatus) else str(job.status),
            "created_at": self._dt_to_str(job.created_at),
            "updated_at": self._dt_to_str(job.updated_at),
            "youtube_url": job.youtube_url or "",
            "source_mode": job.source_mode.value if job.source_mode else SourceMode.ORIGINAL.value,
            "result_mode": job.result_mode.value if job.result_mode else ResultMode.FULL.value,
            "input_wav_path": job.input_wav_path or "",
            "result_path": job.result_path or "",
            "error": job.error or "",
        }
        
        
        
    """
        이건 역 직렬화를 하는 과정
    """
    def _deserialize_job(self, h: Dict[str, Any]) -> Job:
        def g(key: str) -> str:
            v = h.get(key, "")
            if isinstance(v, (bytes, bytearray)):
                return v.decode()
            return str(v) if v is not None else ""

        job_id = g("job_id")
        status_str = g("status") or JobStatus.QUEUED.value

        # ✅ 새 필드 읽기 (없으면 기본값)
        source_mode_str = g("source_mode") or SourceMode.ORIGINAL.value
        result_mode_str = g("result_mode") or ResultMode.FULL.value

        return Job(
            job_id=job_id,
            status=JobStatus(status_str),
            created_at=self._str_to_dt(g("created_at")),
            updated_at=self._str_to_dt(g("updated_at")),
            youtube_url=g("youtube_url") or None,

            # ✅ 여기 변경
            source_mode=SourceMode(source_mode_str),
            result_mode=ResultMode(result_mode_str),

            input_wav_path=g("input_wav_path") or None,
            result_path=g("result_path") or None,
            error=g("error") or None,
        )



    # -----------------------------
    # 포트 관련 코드
    # -----------------------------
    async def create(self, job: Job, *, ttl_seconds: int = 60 * 30) -> None:
        """ 
            이 코드에는 job객체와 ttl시간이 input되고
            job에 key가 할당되며 이 job은 레디스로 넘어간다
        """
        # key를 만든다 이는 위에 만든 redis key만드는 공식에 따라 만들어진다
        key = self._job_key(job.job_id)
        # 레디스 클라이언트에게 이게 이미 존재하는지 물어보고 없으면 0 있으면 1
        exists = await self._r.exists(key)
        if exists:
            raise ValueError(f"Job already exists: {job.job_id}")

        # 이 파이프는 여러 redis명령을 묶기위한 객체
        pipe = self._r.pipeline()
        # 파이프를 세팅한다 그리고 이거를 직렬화해서 매핑한다 기준은 key
        pipe.hset(key, mapping=self._serialize_job(job))
        # 그리고 이 키를 ttl 초후에 삭제한다
        pipe.expire(key, ttl_seconds)
        # 이걸 redis에 보낸다 pipe를 ._r로 레디스 객체로 묶었기 때문에 가능
        await pipe.execute()

    async def get(self, job_id: str) -> Optional[Job]:
        """ 
            이 코드를 통해서 job_id만 있으면 redis 내부에 있는
            현재 상태를 역직렬화 해서 가져온다
        """
        # key에 job_id를 기반으로 그 job_id의 키를 저장한다
        key = self._job_key(job_id)
        # 그 키의 레디스 정보를 모두 가져온다
        h = await self._r.hgetall(key)
        if not h:
            return None
        # 그리고 이거를 역직렬화 ㅎ나다
        return self._deserialize_job(h)

    async def save(self, job: Job, *, ttl_seconds: Optional[int] = None) -> None:
        """
            job과 ttl시간이 input된다
            뭐를 save할지는 모른다 나중에 
            job.mark_done() 이런식으로 job을 바꾸고 여기는 save만 해준다
        """
        key = self._job_key(job.job_id)
        # 이게 존재하는지 확인함
        exists = await self._r.exists(key)
        if not exists:
            raise ValueError(f"Job not found (cannot save): {job.job_id}")
        # 똑같이 파이프라인 만들고 현재상태를 매핑함 직렬화 해서
        pipe = self._r.pipeline()
        pipe.hset(key, mapping=self._serialize_job(job))
        if ttl_seconds is not None:
            pipe.expire(key, ttl_seconds)
        await pipe.execute()
    
    async def delete(self, job_id: str) -> None:
        # 삭제한다 job을 삭제한다
        await self._r.delete(self._job_key(job_id))
    # -----------------------------
    # queue 관련 코드
    # -----------------------------
    
    # youtube queue
    # 설정한 여기 queue에는 워커에서 선언할 queue name이 들어간다
    # 그리고 prefix
    def _queue_key(self, queue: str) -> str:
        return f"{self._p}queue:{queue}"

    # job_id와 queue를 기준으로 job_id를 queue 에 집어넣음
    # 그렇게 만든 job_id와 큐
    async def enqueue(self, queue: str, job_id: str) -> None:
        qk = self._queue_key(queue)
        await self._r.lpush(qk, job_id)
    
    # queue 이름과 timeseconds(최대 대기한도)를 기준으로 dequeue함
    # 일단 qk로 queue_key를 찾음 그리고
    # 그리고 시간이 지나면 dequeue 해라 라는뜻임
    # 여기서 timeout_second 이건 그냥 worker가 얼마만큼 꺠느냐
    
    async def dequeue(self, queue: str, *, timeout_seconds: int = 5) -> Optional[str]:
        qk = self._queue_key(queue)
        item = await self._r.brpop(qk, timeout=timeout_seconds)
        if not item:
            return None
        _, raw = item
        # Redis에서 꺼낸 값이 bytes일 수도, str일 수도 있어서, 항상 str로 통일하기 위한 코드
        return raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
    
    # submitted queue
    
    async def enqueue_submitted(self, job_id: str) -> None:
        qk = self._queue_key("submitted")
        await self._r.lpush(qk, job_id)

    async def dequeue_submitted(self, *, timeout_seconds: int = 3) -> str | None:
        qk = self._queue_key("submitted")
        item = await self._r.brpop(qk, timeout=timeout_seconds)
        if not item:
            return None
        _, job_id = item
        return job_id.decode() if isinstance(job_id, (bytes, bytearray)) else str(job_id)



    # -----------------------------
    # Lock API
    # -----------------------------
    """
        락을 잡는 키다ㅏ
        lk 에 lock_key를 만든다 lock:job:job_id 이런시이었던가 
    """
    async def acquire_lock(
        self,
        job_id: str,
        *,
        token: str,
        ttl_seconds: int = 60 * 10,
    ) -> bool:
        lk = self._lock_key(job_id)
        # 만약 lk라는 키로 락을 잡아본다 nx는 이미 있으면 실패라는 뜻
        """  
            key   = "lock:job:123"
            value = "a1b2c3-token"
            ttl   = 60
        """
        ok = await self._r.set(lk, token, nx=True, ex=ttl_seconds)
        return bool(ok)
    
    async def release_lock(self, job_id: str, *, token: str) -> bool:
        """  
            lua 함수가 나온다 이건 만약 토큰과 내 락을 비교했는데 일치하면 푼다는 말이다
        """
        lk = self._lock_key(job_id)
        # eval 은 lus 스크립트를 내부에서 실행하라는 말이다
        res = await self._r.eval(_UNLOCK_LUA, 1, lk, token)
        return int(res) == 1
    # ttl 시간을 변경함
    async def touch_ttl(self, job_id : str, *, ttl_seconds: int) -> None:
        key = self._job_key(job_id)
        await self._r.expire(key, ttl_seconds)
        
        
    # -----------------------------
    # Submitted
    # -----------------------------
    def _submitted_key(self) -> str:
        return f"{self._p}set:submitted"

    async def add_submitted(self, job_id: str) -> None:
        """
            submit후에 호출함
        """
        sk = self._submitted_key()
        await self._r.sadd(sk, job_id)

    async def remove_submitted(self, job_id: str) -> None:
        """
            done/failed후에 호출함
        """
        sk = self._submitted_key()
        await self._r.srem(sk, job_id)

    async def sample_submitted(self, n: int = 10) -> List[str]:
        """
            랜덤으로 n개 샘플링해서 반환함
        """
        if n <= 0:
            return []

        sk = self._submitted_key()
        # sk중에 랜덤으로 n개만큼 raw_items에 집어넣음
        raw_items = await self._r.srandmember(sk, n)

        # 무조건 n개에 대한 맞춤
        if raw_items is None:
            return []
        if isinstance(raw_items, (bytes, bytearray, str)):
            raw_items = [raw_items]

        out: List[str] = []
        for x in raw_items:
            if isinstance(x, (bytes, bytearray)):
                out.append(x.decode())
            else:
                out.append(str(x))
        return out
