from __future__ import annotations

import asyncio
import os
import uuid
import traceback
from dataclasses import dataclass, replace, asdict
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as redis
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. 환경 변수 로드
load_dotenv()

from shared.dtos.ml_ml_dto import MLProcessRequestDTO
from app.application.services.text_normalize import normalize_text
from app.adapters.jobs.job_store_redis import RedisJobStore
from app.adapters.youtube.youtube_download_adapter import YtDlpYoutubeAudioDownloader
from app.domain.jobs_domain import Job, JobStatus

# --- [설정값] ---
QUEUE_NAME = "youtube"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BASE_URL = (os.getenv("SUPABASE_STORAGE_BASE_URL") or "").rstrip("/")

# Supabase 클라이언트 설정
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@dataclass(frozen=True)
class WorkerConfig:
    redis_url: str
    key_prefix: str = "bass:"
    queue_name: str = QUEUE_NAME
    cookies_path: Path | None = None
    job_ttl_seconds: int = 60 * 30
    lock_ttl_seconds: int = 60 * 10
    storage_root: Path = Path(os.getenv("STORAGE_ROOT", "./storage"))

class MLSubmitClient:
    def __init__(self, store: RedisJobStore) -> None:
        self._store = store

    async def submit(self, *, job_id: str) -> None:
        # [신호탄] bass:queue:process 리스트에 job_id 문자열만 삽입
        await self._store.enqueue("process", job_id)
        print(f"[submit-worker] ✅ ML 분석 큐(process)에 ID 삽입 완료: {job_id}")

def _log_step(msg: str) -> None:
    print(f"[submit-worker] {msg}")

def _safe_strip(v: object | None) -> str:
    return str(v).strip() if v else ""

def _ensure_result_id(*, job: Job) -> tuple[Job, str]:
    rid = _safe_strip(getattr(job, "result_id", None))
    if rid: return job, rid
    rid = uuid.uuid4().hex
    try:
        return replace(job, result_id=rid), rid
    except:
        object.__setattr__(job, "result_id", rid)
        return job, rid
    
# 실제로 job을 토대로 작업
async def process_one_job(
    job_id: str,
    store: RedisJobStore,
    downloader: YtDlpYoutubeAudioDownloader,
    ml: MLSubmitClient,
    cfg: WorkerConfig,
) -> None:
    _log_step(f"🚀 작업 시작: {job_id}")
    job = await store.get(job_id)
    
    if not job or job.status != JobStatus.QUEUED:
        _log_step(f"⚠️ 작업을 찾을 수 없거나 상태가 QUEUED가 아님: {job_id}")
        return

    token = uuid.uuid4().hex
    if not await store.acquire_lock(job_id, token=token, ttl_seconds=cfg.lock_ttl_seconds):
        _log_step(f"🔒 락 획득 실패: {job_id}")
        return

    try:
        youtube_url = _safe_strip(getattr(job, "youtube_url", None))
        job, result_id = _ensure_result_id(job=job)
        
        # 경로 정의
        supabase_path = f"results/{result_id}/audio/original.mp3"
        output_dir_path = f"results/{result_id}/"
        full_input_url = f"{BASE_URL}/{supabase_path}"
        full_output_url = f"{BASE_URL}/{output_dir_path}"

        # 1. 파일 처리 (유튜브 다운로드 및 Supabase 업로드)
        if youtube_url != "MANUAL_UPLOAD":
            _log_step(f"📥 유튜브 다운로드 시작: {youtube_url}")
            local_path = cfg.storage_root / "results" / result_id / "audio" / "temp_yt.wav"
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            produced = await downloader.download_wav(url=youtube_url, output_path=local_path)

            _log_step("📡 Supabase에 파일 업로드 중...")
            with open(produced, "rb") as f:
                supabase.storage.from_("bass_project").upload(
                    path=supabase_path,
                    file=f.read(),
                    file_options={"content-type": "audio/mpeg", "upsert": "true"},
                )
            _log_step("✅ 업로드 완료.")
            
            if local_path.exists():
                os.remove(local_path)
        else:
            _log_step("📂 MANUAL_UPLOAD 확인. 기존 경로를 사용합니다.")

        # 2. dto에 맞게 보낼정보 만들지앗
        submit_data = MLProcessRequestDTO  (
            job_id=job.job_id,
            song_id= job.song_id,
            result_id= job.result_id,
            input_wav_path= full_input_url,
            result_path= full_output_url,
            norm_title= normalize_text(getattr(job, "title", "Unknown")),
            norm_artist= normalize_text(getattr(job, "artist", "Unknown")),
        )

        
        ml_key = f"{cfg.key_prefix}ml:job:{job_id}"
        _log_step(f"ml_key 생성 ml서버를 위한 데이터 여기에 모음: {ml_key}")
        
        await store._r.hset(ml_key, mapping=submit_data.model_dump()) 
        await store._r.expire(ml_key, cfg.job_ttl_seconds)

        await ml.submit(job_id=job_id)


        # 5. 메인 서버용 Job 상태 업데이트
        job.mark_submitted()
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
        await store.add_submitted(job_id)
        _log_step(f"✨ 작업 처리 및 ML 서버 전송 완료: {job_id}")

    except Exception as e:
        _log_step(f"❌ 에러 발생: {str(e)}")
        traceback.print_exc()
        job.mark_failed(error=str(e))
        await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
    finally:
        await store.release_lock(job_id, token=token)

# --- [메인 루프 및 실행부] ---
async def worker_loop(cfg: WorkerConfig) -> None:
    r = redis.from_url(cfg.redis_url, decode_responses=True)
    await r.ping()
    _log_step("🔌 Redis 연결 성공.")

    store = RedisJobStore(r, key_prefix=cfg.key_prefix)
    downloader = YtDlpYoutubeAudioDownloader(debug=True, cookies_path=cfg.cookies_path)
    ml = MLSubmitClient(store)

    _log_step(f"main_server로부터 job생성 대기 시작")
    
    try:
        while True:
            jid = await store.dequeue(cfg.queue_name, timeout_seconds=3)
            if jid:
                await process_one_job(jid, store, downloader, ml, cfg)
            await asyncio.sleep(0.1) 
    except (asyncio.CancelledError, KeyboardInterrupt):
        _log_step("🛑 워커 종료 중...")
    finally:
        await r.aclose()
        _log_step("👋 Redis 연결 종료.")

def main() -> None:
    cfg = WorkerConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix=os.getenv("JOB_KEY_PREFIX", "bass:"),
        cookies_path=Path(os.getenv("YTDLP_COOKIEFILE")) if os.getenv("YTDLP_COOKIEFILE") else None,
    )
    try:
        asyncio.run(worker_loop(cfg))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()