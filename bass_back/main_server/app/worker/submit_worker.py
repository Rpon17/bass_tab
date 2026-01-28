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
    key_prefix: str = "job:"              # 너는 key_prefix를 job:로 쓰고 있음
    queue_name: str = QUEUE_NAME
    job_ttl_seconds: int = 60 * 30

    # ✅ yt-dlp 다운로드가 60초 넘는 경우가 흔해서 기본값을 상향(중복처리 방지)
    lock_ttl_seconds: int = 60 * 10

    output_dir: Path = Path("./data/youtube")


# 이벤트루프를 종료하게 만드는 것
class GracefulShutdown:
    def __init__(self) -> None:
        self._stop = asyncio.Event()

    def install(self) -> None:
        # ✅ running loop를 잡는 게 더 안전함(특히 asyncio.run 컨텍스트)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
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
async def process_one_job(
    *,
    job_id: str,
    store: RedisJobStore,
    downloader: YtDlpYoutubeAudioDownloader,
    cfg: WorkerConfig,
) -> None:
    job = await store.get(job_id)
    if not job:
        return

    # 잡이 q여야만 가능함
    if job.status != JobStatus.QUEUED:
        return

    # 토큰 발급하고
    token: str | None = None
    locked = False

    try:
        token = uuid.uuid4().hex
        # 지금 이거는 이 토큰을가진 이 job_id가 쓰고있다고 락잠금
        locked = await store.acquire_lock(job_id, token=token, ttl_seconds=cfg.lock_ttl_seconds)
        if not locked:
            return

        # url 못찾는 예외처리
        url = job.youtube_url
        if not url:
            job.mark_failed(error="missing youtube_url")
            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
            return

        # ✅ (선택) 다운로드 시작을 RUNNING으로 표시하고 싶으면 여기서 mark_running()
        #     지금은 너가 SUBMITTED를 쓰니까 일단 유지해도 됨
        # job.mark_running()
        # await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

        # 일단 다운로드할파일 국밥파일로 만들고 무거운 ylt작업 실햄함
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = cfg.output_dir / f"{job_id}.wav"

        wav_path = await downloader.download_wav(url=url, output_path=out_path)

        # 다움로드된 wav파일을 job에 저장함
        job.input_wav_path = str(wav_path)

        # 이게 되었으니 바로 ml_server로 보냄
        # ✅ 전제: JobStatus.SUBMITTED / job.mark_submitted() 가 도메인에 있어야 함
        job.mark_submitted()
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

        # 이 job_id는 바로 submitted에 저장함
        await store.add_submitted(job_id)

    except Exception as e:
        job.mark_failed(error=str(e))
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

        # 실패라면 submitted에 넣지않음
        try:
            await store.remove_submitted(job_id)
        except Exception:
            pass

    finally:
        # 이제 락 풀음
        if token and locked:
            try:
                ok = await store.release_lock(job_id, token=token)
                # ✅ release 실패는 큰 사고(토큰 mismatch/TTL 만료)일 수 있어서 최소 로그는 남기는 게 좋음
                # print(f"[WARN] release_lock failed job_id={job_id}")  # 필요하면 로그로 교체
                _ = ok
            except Exception:
                # release 자체가 실패해도 워커 전체는 죽이지 않음
                pass


# 워커가 실행되는 동안 유지될 비동기 메인 루프
# 설정(redis url, queue name, output dir, ttl 등)은 cfg로 묶어서 전달
async def worker_loop(cfg: WorkerConfig) -> None:
    r = redis.from_url(cfg.redis_url)
    # 실제로 되는지 확인함
    await r.ping()

    # strore와 downloader에 직접만든 adapter기능 주입
    store = RedisJobStore(r, key_prefix=cfg.key_prefix)
    downloader = YtDlpYoutubeAudioDownloader()

    # SIGINT(Ctrl+C), SIGTERM(docker stop 등)을 받으면
    # shutdown.stop_event가 set 되도록 신호 핸들러를 등록
    shutdown = GracefulShutdown()
    shutdown.install()

    try:
        # stop_event가 set될 때까지 계속 돈다
        # 즉 종료요청이 오면 자연스럽게 종료됨
        while not shutdown.stop_event.is_set():
            # job_id하나 redis내부큐에서 dequeue해서 빼옴
            job_id = await store.dequeue(cfg.queue_name, timeout_seconds=3)
            if not job_id:
                continue
            # 가져온 job_id시행
            await process_one_job(job_id=job_id, store=store, downloader=downloader, cfg=cfg)

    #  레디스 연결정리
    finally:
        await r.aclose()


# 메인이여 이걸 호출해라
def main() -> None:
    cfg = WorkerConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("JOB_KEY_PREFIX", "job:"),
        output_dir=Path(os.getenv("YOUTUBE_OUTPUT_DIR", "./data/youtube")),
    )
    asyncio.run(worker_loop(cfg))


if __name__ == "__main__":
    main()
