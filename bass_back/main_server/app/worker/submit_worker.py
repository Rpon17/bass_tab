from __future__ import annotations

import asyncio
import os
import signal
import traceback
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import redis.asyncio as redis
from dotenv import load_dotenv
from supabase import create_client, Client

# .env 로드
load_dotenv()

from app.adapters.jobs.job_store_redis import RedisJobStore
from app.adapters.youtube.youtube_download_adapter import YtDlpYoutubeAudioDownloader
from app.domain.jobs_domain import Job, JobStatus
from app.application.services.text_normalize import normalize_text

# 설정값
QUEUE_NAME = "youtube"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
clean_base_url = (os.getenv("SUPABASE_STORAGE_BASE_URL") or "").rstrip("/")

# Supabase 클라이언트
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@dataclass(frozen=True)
class WorkerConfig:
    redis_url: str
    key_prefix: str = "bass:"
    ml_key_prefix: str = "bass:ml:"
    queue_name: str = QUEUE_NAME
    cookies_path: Path | None = None
    job_ttl_seconds: int = 60 * 30
    lock_ttl_seconds: int = 60 * 10
    storage_root: Path = Path(os.getenv("STORAGE_ROOT", "./storage"))


class MLSubmitClient:
    """Redis List(RPUSH)를 사용하여 ML 서버 큐에 작업을 제출합니다."""

    def __init__(self, store: RedisJobStore) -> None:
        # [수정] RedisJobStore.enqueue()를 사용해 키 생성 로직을 일원화
        self._store = store

    async def submit(self, *, job_id: str, **kwargs) -> None:
        print(f"[submit-worker] ML 분석 큐에 삽입: {job_id}")
        # [수정] store.enqueue("process", ...) → "bass:queue:process" 에 LPUSH
        # ml_worker 도 동일하게 store.dequeue("process") 로 BRPOP 하므로 키가 일치함
        await self._store.enqueue("process", job_id)
        print(f"[submit-worker] 삽입 완료")

    async def aclose(self) -> None:
        pass


class GracefulShutdown:
    def __init__(self) -> None:
        self._stop = asyncio.Event()

    def install(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: self._stop.set())

    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop


def _log_step(msg: str) -> None:
    print(f"[submit-worker] {msg}")


def _safe_strip(v: object | None) -> str:
    return str(v).strip() if v else ""


def _validate_url(url: str) -> str:
    """[수정] URL을 저장하기 전에 검증 — 손상된 URL이 저장되는 것을 방지"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"유효하지 않은 URL scheme: {url!r}")
    return url


def _ensure_result_id(*, job: Job) -> tuple[Job, str]:
    rid = _safe_strip(getattr(job, "result_id", None))
    if rid:
        return job, rid
    rid = uuid.uuid4().hex
    try:
        return replace(job, result_id=rid), rid
    except Exception:
        setattr(job, "result_id", rid)
        return job, rid


async def process_one_job(
    job_id: str,
    store: RedisJobStore,
    downloader: YtDlpYoutubeAudioDownloader,
    ml: MLSubmitClient,
    cfg: WorkerConfig,
) -> None:
    _log_step(f"작업 시작: {job_id}")
    job = await store.get(job_id)
    if not job or job.status != JobStatus.QUEUED:
        return

    token = uuid.uuid4().hex
    if not await store.acquire_lock(job_id, token=token, ttl_seconds=cfg.lock_ttl_seconds):
        return

    try:
        youtube_url = _safe_strip(getattr(job, "youtube_url", None))
        job, result_id = _ensure_result_id(job=job)
        
        # [추가] 경로 설정 - ML 서버가 읽을 수 있도록 미리 정의
        supabase_path = f"results/{result_id}/audio/original.mp3"
        output_dir = f"results/{result_id}/"

        # 1. 파일 준비 (유튜브 다운로드 및 Supabase 업로드)
        if youtube_url != "MANUAL_UPLOAD":
            _validate_url(youtube_url)
            _log_step(f"유튜브 다운로드 중: {youtube_url}")
            
            local_path = cfg.storage_root / "results" / result_id / "audio" / "temp_yt.wav"
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            produced = await downloader.download_wav(url=youtube_url, output_path=local_path)

            _log_step("Supabase 업로드 중...")
            with open(produced, "rb") as f:
                supabase.storage.from_("bass_project").upload(
                    path=supabase_path,
                    file=f.read(),
                    file_options={"content-type": "audio/mpeg", "upsert": "true"},
                )
            _log_step("업로드 완료.")
            
            if local_path.exists():
                os.remove(local_path)
        else:
            # [추가] 수동 업로드인 경우, 이미 DB에 경로가 있을 수도 있지만 
            # 확실하게 하기 위해 supabase_path 형식을 맞춰줍니다.
            if not getattr(job, "input_wav_path", None):
                # 수동 업로드 시의 기본 경로 규칙이 있다면 여기 적어줍니다.
                pass

        # ⭐ [핵심 수정] Job 객체에 정보를 업데이트합니다!
        # replace를 사용해 input_wav_path와 output_dir(또는 result_path)를 채워줍니다.
        job = replace(job, 
                     input_wav_path=supabase_path, 
                     output_dir=output_dir)

        # 2. Redis에 업데이트된 Job 저장
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

        # 3. 그 다음에 ML 큐에 작업 제출 (이제 ML 서버가 경로를 읽을 수 있음)
        await ml.submit(job_id=job_id)

        job.mark_submitted()
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
        await store.add_submitted(job_id)

    except Exception as e:
        traceback.print_exc()
        job.mark_failed(error=str(e))
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
    finally:
        await store.release_lock(job_id, token=token)


async def worker_loop(cfg: WorkerConfig) -> None:
    r = redis.from_url(cfg.redis_url, decode_responses=True)
    await r.ping()

    store = RedisJobStore(r, key_prefix=cfg.key_prefix)
    downloader = YtDlpYoutubeAudioDownloader(debug=True, cookies_path=cfg.cookies_path)
    # [수정] MLSubmitClient에 store를 전달 — enqueue() 로직 일원화
    ml = MLSubmitClient(store)

    shutdown = GracefulShutdown()
    shutdown.install()

    _log_step("Worker Loop 실행 중...")
    try:
        while not shutdown.stop_event.is_set():
            jid = await store.dequeue(cfg.queue_name, timeout_seconds=3)
            if jid:
                await process_one_job(jid, store, downloader, ml, cfg)
    finally:
        await r.aclose()


def main() -> None:
    storage_root = Path(os.getenv("STORAGE_ROOT", "./storage"))
    storage_root.mkdir(parents=True, exist_ok=True)

    cfg = WorkerConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("JOB_KEY_PREFIX", "bass:"),
        ml_key_prefix=os.getenv("ML_JOB_KEY_PREFIX", "bass:ml:"),
        cookies_path=Path(os.getenv("YTDLP_COOKIEFILE")) if os.getenv("YTDLP_COOKIEFILE") else None,
        storage_root=storage_root,
    )
    asyncio.run(worker_loop(cfg))


if __name__ == "__main__":
    main()
