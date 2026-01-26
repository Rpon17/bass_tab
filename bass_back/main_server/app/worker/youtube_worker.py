from __future__ import annotations

import asyncio
import os
import signal
import uuid
from dataclasses import dataclass
from pathlib import Path

import redis.asyncio as redis

from bass_back.main_server.app.domain.jobs_domain import JobStatus
from bass_back.main_server.app.adapters.jobs.job_store_redis import RedisJobStore
from bass_back.main_server.app.adapters.youtube.youtube_download_adapter import YtDlpYoutubeAudioDownloader


QUEUE_NAME = "youtube"


@dataclass(frozen=True)
class WorkerConfig:
    redis_url: str
    key_prefix: str = "job:"             
    queue_name: str = QUEUE_NAME
    job_ttl_seconds: int = 60 * 30
    lock_ttl_seconds: int = 60
    output_dir: Path = Path("./data/youtube")

# 이벤트루프를 종료하게 만드는 것
class GracefulShutdown:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
    
    def install(self) -> None:
        # loop 는 이벤트루프 를 가져옴
        loop = asyncio.get_event_loop()
        # 종료시그널이 오면
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                # self._stop.set을 저장함 이는 on으로 바꿔서 워커에게 그만하라 보내는것
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: self._stop.set())
    
    # 외부에서 read전용식으로 하게 만듬
    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop

# 워커 전용 유스케이스를 모아놓음 워커가 할 일 리스트
""" 
    job_id: 큐에서 꺼낸 식별자
    store: Redis 기반 JobStore (상태/락/TTL 관리)
    downloader: yt-dlp 어댑터
    cfg: 워커 설정 묶음
"""
async def process_one_job(*, job_id: str, store: RedisJobStore, downloader: YtDlpYoutubeAudioDownloader, cfg: WorkerConfig) -> None:
    # stor에서 job을 가져옴
    job = await store.get(job_id)
    # job이 없으면 무시하고 종료함
    if not job:
        return
    # 만약 job 상태가 queue되지 않아도 무시하고 종료
    if job.status != JobStatus.QUEUED:
        return

    # redis에 맞게 토큰 발급(락전용)
    token = uuid.uuid4().hex
    # lock에는 job_id와 토큰 그리고 ttl_seconds를기반으로 lock을 잡음
    locked = await store.acquire_lock(job_id, token=token, ttl_seconds=cfg.lock_ttl_seconds)
    if not locked:
        return

    try:
        # 그리고 running상태로 시도하고 이거를 상태 저장함
        job.mark_running()
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

        # url은 job에 저장된 url 
        url = job.youtube_url
        if not url:
            # url이 없으면 실패에러처리하고 상태저장
            job.mark_failed(error="missing youtube_url")
            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
            return
        # 그리고 출력 디렉토리 준비
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = cfg.output_dir / f"{job_id}.wav"

        # 실제로 무거운 작업 실시
        wav_path = await downloader.download_wav(url=url, output_path=out_path)

        # DONE으로 상태 바꾸고 저장함
        job.mark_done(result_path=str(wav_path))
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

    # 예외가 생기면 ERROR 내고 저장
    except Exception as e:
        job.mark_failed(error=str(e))
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
    # 마지막으로 락을 해제함
    finally:
        await store.release_lock(job_id, token=token)

# 워커가 실행되는 동안 유지될 비동기 메인 루프
# 설정(redis url, queue name, output dir, ttl 등)은 cfg로 묶어서 전달
async def worker_loop(cfg: WorkerConfig) -> None:
    # redis.from_url(...)로 Redis 클라이언트를 생성
    r = redis.from_url(cfg.redis_url)
    # 실제로 연결되는지 확인
    await r.ping()

    # strore와 downloader에 직접만든 adapter기능 주입
    store = RedisJobStore(r, key_prefix=cfg.key_prefix)
    downloader = YtDlpYoutubeAudioDownloader()

    # SIGINT(Ctrl+C), SIGTERM(docker stop 등)을 받으면
    # shutdown.stop_event가 set 되도록 신호 핸들러를 등록
    shutdown = GracefulShutdown()
    shutdown.install()
    """ 
        dequeue는 워커가 할 일이 생길 때까지 기다리는 동작이고,
        enqueue는 다른 프로세스(API 서버)가 job을 등록할 때 발생합니다.
    """
    try:
        # stop_event가 set될 때까지 계속 돈다
        # 즉 종료요청이 오면 자연스럽게 종료됨
        while not shutdown.stop_event.is_set():
            # 큐에있던 잡을 하나 뺴옴
            job_id = await store.dequeue(cfg.queue_name, timeout_seconds=3)
            # 없으면 뭐 하지말고 기다려
            if not job_id:
                continue
            # 뺴온 job을 가지고 작업을 실행함
            await process_one_job(job_id=job_id, store=store, downloader=downloader, cfg=cfg)
    # 레디스 연결을 정리해라
    finally:
        await r.aclose()


def main() -> None:
    cfg = WorkerConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("JOB_KEY_PREFIX", "job:"),
        output_dir=Path(os.getenv("YOUTUBE_OUTPUT_DIR", "./data/youtube")),
    )
    asyncio.run(worker_loop(cfg))


if __name__ == "__main__":
    main()
