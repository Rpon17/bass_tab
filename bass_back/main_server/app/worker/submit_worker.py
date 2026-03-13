from __future__ import annotations

import asyncio
import os
import signal
import traceback
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import httpx
import redis.asyncio as redis

from app.adapters.jobs.job_store_redis import RedisJobStore
from app.adapters.youtube.youtube_download_adapter import YtDlpYoutubeAudioDownloader
from app.domain.jobs_domain import Job, JobStatus
from shared.dtos.ml_ml_dto import MLProcessRequestDTO
from app.application.services.text_normalize import normalize_text

QUEUE_NAME: str = "youtube"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log_step(message: str) -> None:
    print(f"[submit-worker] {message}")


def _log_kv(key: str, value: object) -> None:
    print(f"[submit-worker]   {key}: {value}")


@dataclass(frozen=True)
class WorkerConfig:
    redis_url: str
    key_prefix: str = "bass:"
    queue_name: str = QUEUE_NAME
    cookies_path: Path | None = None
    job_ttl_seconds: int = 60 * 30
    lock_ttl_seconds: int = 60 * 10
    storage_root: Path = Path(r"C:\bass_project\storage")
    ml_server_base_url: str = "http://127.0.0.1:8001"
    ml_submit_timeout_seconds: float = 30.0


class GracefulShutdown:
    def __init__(self) -> None:
        self._stop: asyncio.Event = asyncio.Event()

    def install(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: self._stop.set())  # type: ignore[arg-type]

    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop


class MLSubmitClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 30.0) -> None:
        self._base_url: str = base_url.rstrip("/")
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def submit(
        self,
        *,
        job_id: str,
        song_id: str,
        result_id: str,
        input_wav_path: str,
        result_path: str,
        norm_title: str,
        norm_artist: str,
    ) -> None:
        url: str = f"{self._base_url}/v1/process"

        req: MLProcessRequestDTO = MLProcessRequestDTO(
            job_id=job_id,
            song_id=song_id,
            result_id=result_id,
            input_wav_path=input_wav_path,
            result_path=result_path,
            norm_title=norm_title,
            norm_artist=norm_artist,
        )

        _log_step("ML submit request 생성 완료")
        _log_kv("url", url)
        _log_kv("body", req.model_dump())

        r: httpx.Response = await self._client.post(url, json=req.model_dump())

        _log_step("ML submit 응답 수신 완료")
        _log_kv("status_code", r.status_code)
        _log_kv("response_text", r.text)

        r.raise_for_status()


def _make_result_path(*, result_id: str) -> str:
    return f"results/{result_id}"


def _result_dir_from_path(*, cfg: WorkerConfig, result_path: str) -> Path:
    return cfg.storage_root / Path(result_path)


def _safe_strip(v: object | None) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _ensure_result_id(*, job: Job) -> tuple[Job, str]:
    rid: str = _safe_strip(getattr(job, "result_id", None))
    if rid:
        return job, rid

    rid = uuid.uuid4().hex

    try:
        setattr(job, "result_id", rid)
        return job, rid
    except Exception:
        try:
            new_job: Job = replace(job, result_id=rid)
            return new_job, rid
        except Exception:
            return job, rid


async def process_one_job(
    *,
    job_id: str,
    store: RedisJobStore,
    downloader: YtDlpYoutubeAudioDownloader,
    ml: MLSubmitClient,
    cfg: WorkerConfig,
) -> None:
    _log_step("job 처리 시작")
    _log_kv("job_id", job_id)

    job: Job | None = await store.get(job_id)
    if not job:
        _log_step("job 조회 실패 - job 없음")
        return

    if job.status != JobStatus.QUEUED:
        _log_step("job 스킵 - QUEUED 상태 아님")
        return

    token: str | None = None
    locked: bool = False

    try:
        token = uuid.uuid4().hex
        locked = await store.acquire_lock(job_id, token=token, ttl_seconds=cfg.lock_ttl_seconds)

        if not locked:
            _log_step("lock 획득 실패")
            return

        job = await store.get(job_id)
        if not job or job.status != JobStatus.QUEUED:
            return

        youtube_url: str = _safe_strip(getattr(job, "youtube_url", None))
        title: str = _safe_strip(getattr(job, "title", None))
        artist: str = _safe_strip(getattr(job, "artist", None))
        song_id: str = _safe_strip(getattr(job, "song_id", None))

        if not youtube_url or not title or not artist or not song_id:
            job.mark_failed(error="missing fields")
            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
            return

        norm_title: str = normalize_text(title)
        norm_artist: str = normalize_text(artist)

        job, result_id = _ensure_result_id(job=job)
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

        result_path: str = _make_result_path(result_id=result_id)
        result_dir: Path = _result_dir_from_path(cfg=cfg, result_path=result_path)

        audio_dir: Path = result_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        original_wav_path: Path = audio_dir / "original.wav"

        produced_path: Path = await downloader.download_wav(
            url=youtube_url,
            output_path=original_wav_path,
        )

        if not produced_path.exists():
            raise FileNotFoundError(str(produced_path))

        await ml.submit(
            job_id=job_id,
            song_id=song_id,
            result_id=result_id,
            input_wav_path=str(produced_path),
            result_path=result_path,
            norm_title=norm_title,
            norm_artist=norm_artist,
        )

        job.mark_submitted()
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)

        await store.add_submitted(job_id)

    except Exception as e:
        traceback.print_exc()

        try:
            job2: Job | None = await store.get(job_id)
            if job2:
                job2.mark_failed(error=str(e))
                await store.save(job2, ttl_seconds=cfg.job_ttl_seconds)
        except Exception:
            pass

    finally:
        if token and locked:
            try:
                await store.release_lock(job_id, token=token)
            except Exception:
                pass


async def worker_loop(cfg: WorkerConfig) -> None:
    r: redis.Redis = redis.from_url(cfg.redis_url)
    await r.ping()

    store: RedisJobStore = RedisJobStore(r, key_prefix=cfg.key_prefix)

    downloader: YtDlpYoutubeAudioDownloader = YtDlpYoutubeAudioDownloader(
        debug=True,
        cookies_path=cfg.cookies_path,
    )

    ml: MLSubmitClient = MLSubmitClient(
        cfg.ml_server_base_url,
        timeout_seconds=cfg.ml_submit_timeout_seconds,
    )

    shutdown: GracefulShutdown = GracefulShutdown()
    shutdown.install()

    try:
        while not shutdown.stop_event.is_set():
            jid: str | None = await store.dequeue(cfg.queue_name, timeout_seconds=3)
            if not jid:
                continue

            await process_one_job(
                job_id=jid,
                store=store,
                downloader=downloader,
                ml=ml,
                cfg=cfg,
            )
    finally:
        await ml.aclose()
        await r.aclose()


def _require_env(name: str) -> str:
    v: str | None = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env: {name}")
    return v.strip()


def main() -> None:
    storage_root: Path = Path(_require_env("STORAGE_ROOT"))

    cookies_env: str | None = os.getenv("YTDLP_COOKIEFILE")
    cookies_path: Path | None = Path(cookies_env) if cookies_env else None

    cfg: WorkerConfig = WorkerConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("JOB_KEY_PREFIX", "bass:"),
        cookies_path=cookies_path,
        storage_root=storage_root,
        ml_server_base_url=os.getenv("ML_SERVER_URL", "http://127.0.0.1:8001"),
        ml_submit_timeout_seconds=float(os.getenv("ML_SUBMIT_TIMEOUT", "30.0")),
    )

    asyncio.run(worker_loop(cfg))


if __name__ == "__main__":
    main()