from __future__ import annotations

import asyncio
import os
import signal
import traceback
import uuid
import requests
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from supabase import create_client, Client

import httpx
import redis.asyncio as redis
from dotenv import load_dotenv

# .env 파일 로드 (가장 먼저 수행)
load_dotenv()

from app.adapters.jobs.job_store_redis import RedisJobStore
from app.adapters.youtube.youtube_download_adapter import YtDlpYoutubeAudioDownloader
from app.domain.jobs_domain import Job, JobStatus
from shared.dtos.ml_ml_dto import MLProcessRequestDTO
from app.application.services.text_normalize import normalize_text

QUEUE_NAME: str = "youtube"
BASE_URL = os.getenv("SUPABASE_STORAGE_BASE_URL")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_STORAGE_BASE_URL=os.getenv("SUPABASE_STORAGE_BASE_URL")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ 경고: .env에 SUPABASE_URL 또는 KEY가 없습니다!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
clean_base_url = (os.getenv("SUPABASE_STORAGE_BASE_URL") or "").rstrip("/")

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
    storage_root: Path = Path(os.getenv("STORAGE_ROOT", "./storage"))
    supabase_url : str = clean_base_url
    ml_server_base_url: str = os.getenv("ML_SERVER_URL", "http://127.0.0.1:8001")
    ml_submit_timeout_seconds: float = float(os.getenv("ML_SUBMIT_TIMEOUT", "30.0"))


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

        _log_step(f"result_path={result_path}")
        _log_step("ML submit 응답 수신 완료")
        _log_kv("status_code", r.status_code)
        _log_kv("response_text", r.text)

        r.raise_for_status()


def _make_result_path(*, cfg: WorkerConfig, result_id: str) -> str:
    return str((cfg.storage_root / "results" / result_id).absolute())


def _safe_strip(v: object | None) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _ensure_result_id(*, job: Job) -> tuple[Job, str]:
    # 1. 우선 기존에 저장된 ID가 있는지 확인해 (직접 업로드 케이스)
    rid: str = _safe_strip(getattr(job, "result_id", None))
    
    if rid:
        # 이미 있다면 그대로 반환 (이게 정상적인 업로드 흐름!)
        return job, rid

    # 2. 만약 없다면? (유튜브 링크 케이스 등) 새로 하나 생성해!
    rid = uuid.uuid4().hex
    _log_step(f"기존 ID가 없어서 새로 생성했습니다: {rid}")

    # 3. 새로 만든 ID를 Job 객체에 안전하게 심어주기
    try:
        # 데이터클래스일 경우
        new_job = replace(job, result_id=rid)
        return new_job, rid
    except Exception:
        # 일반 객체일 경우
        try:
            setattr(job, "result_id", rid)
            return job, rid
        except Exception:
            # 둘 다 안 되면 그냥 값만이라도 반환
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

        result_path: str = _make_result_path(cfg=cfg, result_id=result_id)
        result_dir: Path = Path(result_path)

        audio_dir: Path = result_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        supabase_dir = f"/results/{result_id}/audio/original.mp3"
        output_dir = f"/results/{result_id}"
        local_temp_path = audio_dir / "temp_yt.wav"
        
        # URL 생성
        original_wav_path = f"{clean_base_url}{supabase_dir}"
        output_path = f"{clean_base_url}{output_dir}"

        # --- [STEP 1: 파일 준비 및 업로드] ---
        if youtube_url == "MANUAL_UPLOAD":
            _log_step("직접 업로드된 파일 확인됨. 업로드 단계를 건너뜁니다.")
        else:
            _log_step(f"유튜브 다운로드 시작: {youtube_url}")
            produced_path = await downloader.download_wav(
                url=youtube_url,
                output_path=local_temp_path,
            )
            
            _log_step("📡 로컬 파일을 Supabase로 업로드 중...")
            with open(produced_path, "rb") as f:
                # 여기서 업로드가 완료될 때까지 블로킹됩니다.
                supabase.storage.from_("bass_project").upload(
                    path=supabase_dir.lstrip("/"),
                    file=f.read(),
                    file_options={"content-type": "audio/mpeg", "upsert": "true"}
                )
            _log_step("✅ Supabase 업로드 완료")
            _log_step("⏳ 스토리지 안정화를 위해 10초간 대기합니다 (Safety Delay)...")
            await asyncio.sleep(10.0)

        # --- [STEP 2: ML 서버에 주문 넣기] ---
        # 파일이 확실히 업로드된 후(또는 이미 존재하는 확인 후)에만 실행됩니다.
        _log_step("🚀 ML 서버에 분석 작업 제출")
        await ml.submit(
            job_id=job_id,
            song_id=song_id,
            result_id=result_id,
            input_wav_path=str(original_wav_path), 
            result_path=str(output_path),
            norm_title=norm_title,
            norm_artist=norm_artist,
        )
        
        _log_kv("DEBUG_original_wav_path", original_wav_path)
        job.mark_submitted()
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
        await store.add_submitted(job_id)
        
        # 로컬 정리
        if youtube_url != "MANUAL_UPLOAD" and local_temp_path.exists():
            os.remove(local_temp_path)
            _log_step("🗑️ 로컬 임시 파일 삭제 완료")
            
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
    r: redis.Redis = redis.from_url(cfg.redis_url, decode_responses=True)
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

    _log_step(f"Worker Loop 시작 (Storage: {cfg.storage_root})")

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
        # 💡 배포 시 실수 방지를 위해 에러를 띄워
        raise RuntimeError(f"Missing env: {name}")
    return v.strip()


def main() -> None:
    # 💡 .env에서 읽어온 경로를 기반으로 폴더 생성
    storage_root: Path = Path(_require_env("STORAGE_ROOT"))
    if not storage_root.exists():
        storage_root.mkdir(parents=True, exist_ok=True)

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