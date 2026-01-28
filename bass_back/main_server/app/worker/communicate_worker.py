from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
import redis.asyncio as redis

from bass_back.main_server.app.adapters.jobs.job_store_redis import RedisJobStore
from bass_back.main_server.app.domain.jobs_domain import JobStatus

"""
    그러면 ml_server에서는 작업하면서 상태를 똑같이 submit,done,fail 이렇게 가야된다
"""

# 이 워커에서 사용할 규약들 정리
@dataclass(frozen=True)
class CommunicaterConfig:
    redis_url: str
    job_key_prefix: str = "job:"
    submitted_sample_n: int = 20           # 20개씩 꺼내봄
    poll_interval_seconds: float = 2.0     # 2초마다 한번씩 꺼내봄
    submitted_timeout_minutes: int = 30    # 30분초과시 faiil처리

    ml_server_base_url: str = "http://localhost:8001"
    http_timeout_seconds: float = 10.0

    # 한 루프에서 status 요청을 너무 병렬로 날리지 않도록 제한
    max_concurrent_status_checks: int = 10


# 이벤트 루프 위에서 동작하는 “신호용 플래그”
# self._stop -> 이벤트루프를 종료함
class GracefulShutdown:
    def __init__(self) -> None:
        self._stop = asyncio.Event()

    def install(self) -> None:
        # 이벤트 루프를 가져오는 것
        # ✅ get_event_loop()는 환경에 따라 문제날 수 있어서 running loop를 쓰는 게 안전
        loop = asyncio.get_running_loop()

        # 종료요청을 받으면 stop.set으로 꺼버림
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: self._stop.set())

    # 외부에서 read전용식으로 하게 만듬
    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop


class MLStatusClient:
    """
        일단 접속할 비동기 클라이언트 도구를 만든다 이 도구를 기반으로 정보를 요청할것임

    """

    # 요청받는 base_url과 timeout_seconds를 기준으로
    def __init__(self, base_url: str, *, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        # 비동기 HTTP 요청을 보내는 도구이다
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    # 이건 클라이언트를 끈다
    async def aclose(self) -> None:
        await self._client.aclose()

    #이건 status를 가져오는 함수이다
    async def get_status(self, job_id: str) -> dict:
        """
        예시 endpoint:
          GET {base_url}/v1/status/{job_id}

        기대 응답(예시):
          {
            "status": "queued" | "running" | "done" | "failed",
            "result": {"bass_wav_path": "...", ...}   # done일 때
            "error": "..."                             # failed일 때
          }
        """
        url = f"{self._base_url}/v1/status/{job_id}"

        # 이 url로 get 요청을 보내라
        r = await self._client.get(url)
        # 실패로 처리하고 중단함
        r.raise_for_status()
        # 결과 json파일을 가져옴
        return r.json()


def _utcnow() -> datetime:
    return datetime.utcnow()


#
async def _communicater_one(
    *,
    job_id: str,
    store: RedisJobStore,
    ml: MLStatusClient,
    cfg: CommunicaterConfig,   # ✅ 타입 이름 오타 수정 (communicaterConfig -> CommunicaterConfig)
    # 동시에 실행될 수 있는 비동기 작업의 최대 개수
    sem: asyncio.Semaphore,
) -> None:
    # store에 있는 job
    async with sem:
        # 이 job이 실제로 레디스저장소에 있는가? 없으면 바로 삭제
        job = await store.get(job_id)
        if not job:
            await store.remove_submitted(job_id)
            return

        # 상태가 sub이 아닌것들도 다 제거함 이게 왜들어있어? 넌 바로삭제
        # ✅ JobStatus에 SUBMITTED가 없으니까, "이미 끝난 상태"만 정리하는 방식으로 변경
        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            await store.remove_submitted(job_id)
            return

        # 현재시간이 데드라인을 넘었었다면 실패임 그리고 바로삭제
        deadline = job.updated_at + timedelta(minutes=cfg.submitted_timeout_minutes)
        if _utcnow() > deadline:
            job.mark_failed(error=f"ML processing timeout (> {cfg.submitted_timeout_minutes} min)")
            await store.save(job)
            await store.remove_submitted(job_id)
            return

        # ML 서버에 상태 조회
        try:
            data = await ml.get_status(job_id)
        except Exception as e:
            # 조회 실패해도 다음 poll에서 다시 시도함 어짜피 30분뒤면 자동삭제됨
            return

        # 여기서 status 뒤에있는 단어만 가져옴
        status = str(data.get("status", "")).lower()

        # 만약 끝났다한다
        if status == "done":
            # 거기서 결과를 가져온다
            result = data.get("result") or {}
            # 저장 path도 가져온다
            bass_path = result.get("bass_wav_path") or result.get("result_path") or ""

            # bass path가 있다면
            if bass_path:
                job.mark_done(result_path=str(bass_path))
            else:
                job.mark_failed(error="ML returned done but no result path")
            # 끝나면 상태 저장하고 submitted에서 삭제한다
            await store.save(job)
            await store.remove_submitted(job_id)
            return

        # 만약 실패다 그러면 error 항목을 가져온다 그리고 fail처리한다
        if status == "failed":
            err = data.get("error") or "ML processing failed"
            job.mark_failed(error=str(err))
            await store.save(job)
            await store.remove_submitted(job_id)
            return

        # queued/running/unknown 이런건 그대로 둔다 중간상태랄까
        return


# 워커가 실행되는 동안 유지될 비동기 메인 루프
async def communicater_loop(cfg: CommunicaterConfig) -> None:
    r = redis.from_url(cfg.redis_url)
    await r.ping()

    store = RedisJobStore(r, key_prefix=cfg.job_key_prefix)
    ml = MLStatusClient(cfg.ml_server_base_url, timeout_seconds=cfg.http_timeout_seconds)

    # 종료가 오면 끄게 하주는 코드
    shutdown = GracefulShutdown()
    shutdown.install()
    # 최대 가능한 작업개수
    sem = asyncio.Semaphore(cfg.max_concurrent_status_checks)

    try:
        # 꺼지지 않는동안 shutdown이 되지 않는동안 계속 돌거다
        while not shutdown.stop_event.is_set():
            # redis에 있는 submit 배열에서 정한 개수만큼 뺴온다
            job_ids = await store.sample_submitted(cfg.submitted_sample_n)

            """
                job_ids에서 job_id들을 하나하나 jid로 저장함
                그리고 저장한 jid들을 하나하나 꺼내서 배열을 돌린다
            """
            if job_ids:
                tasks = [
                    _communicater_one(job_id=jid, store=store, ml=ml, cfg=cfg, sem=sem)
                    for jid in job_ids
                ]
                # asyncio.gather는 여러 코루틴/태스크를 동시에 실행하고, 모두 끝날 때까지 기다린 뒤 결과를 모아준다.
                await asyncio.gather(*tasks, return_exceptions=True)
            # 이거를 2초마다 한번씩 해라
            await asyncio.sleep(cfg.poll_interval_seconds)
    # http연결하는 객체와 레디스와 연결하는 객체를 닫아줌
    finally:
        await ml.aclose()
        await r.aclose()


def main() -> None:
    cfg = CommunicaterConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        job_key_prefix=os.getenv("JOB_KEY_PREFIX", "job:"),
        ml_server_base_url=os.getenv("ML_SERVER_URL", "http://localhost:8001"),
    )
    asyncio.run(communicater_loop(cfg))


if __name__ == "__main__":
    main()
