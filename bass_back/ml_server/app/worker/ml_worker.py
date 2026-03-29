from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass

from dotenv import load_dotenv
import redis.asyncio as redis

# 필요한 클래스들 임포트
from app.adapters.job.job_store_redis import RedisJobStore
from app.application.usecases.final_usecase import RunMLProcessUseCase
from app.domain.jobs_domain import MLJobStatus
from app.domain.models_domain import MLJob
from shared.dtos.main_ml_dto import MLProcessRequestDTO

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
logger = logging.getLogger(__name__)

QUEUE_NAME: str = "process"

@dataclass(frozen=True)
class MLWorkerConfig:
    redis_url: str

    key_prefix: str = "bass:ml:"
    queue_name: str = QUEUE_NAME
    job_ttl_seconds: int = 60 * 60

class GracefulShutdown:
    def __init__(self) -> None:
        self._stop: asyncio.Event = asyncio.Event()

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

def build_usecase(*, store: RedisJobStore) -> RunMLProcessUseCase:
    # (기존 임포트 로직 동일)
    from app.adapters.basic_pitch.basic_pitch_adapter import BasicPitchAdapter
    from app.adapters.bpm.bpm_estimate_adapter import LibrosaBpmEstimator
    from app.adapters.demucs.demucs_adapter import DemucsAdapter
    from app.adapters.tab.frame.frame_json_normalization_adapter import FramePitchNormalizeAdapter
    from app.adapters.tab.frame.frame_octave_adapter import FramePitchOctaveNormalizeAdapter
    from app.adapters.tab.merge.original.onset_frame_plus_adapter import OnsetFrameFuseAdapter
    from app.adapters.tab.merge.root.root_note_adapter import RootTabBuildAdapter
    from app.adapters.tab.onset.onset_json_normalization_adapter import OnsetNormalizeAdapter
    from app.adapters.tab.onset.onset_octave_adapter import OnsetPitchOctaveNormalizeAdapter
    from app.adapters.tab.tab.origianal_tab.candidate_adapter import BassTabCandidateBuilderAdapter
    from app.adapters.tab.tab.origianal_tab.original_tab_adapter import OriginalTabGenerateAdapter
    from app.adapters.tab.tab.origianal_tab.viterbi_adapter import BassTabViterbiAdapter
    from app.adapters.tab.tab.root_tab.root_tab_adapter import RootTabGenerateAdapter
    from app.adapters.ml_supabase_adapter import SupabaseAudioHandler

    candidate_builder = BassTabCandidateBuilderAdapter()
    viterbi = BassTabViterbiAdapter()
    handler = SupabaseAudioHandler()

    original_tab_generator = OriginalTabGenerateAdapter(
        candidate_builder=candidate_builder,
        viterbi=viterbi,
        handler=handler,
    )
    root_tab_generator = RootTabGenerateAdapter(
        candidate_builder=candidate_builder,
        handler=handler,
    )

    return RunMLProcessUseCase(
        job_store=store,
        bpm_port=LibrosaBpmEstimator(),
        demucs_port=DemucsAdapter(),
        basic_pitch_port=BasicPitchAdapter(),
        frame_octave_port=FramePitchOctaveNormalizeAdapter(),
        frame_note_normalize_port=FramePitchNormalizeAdapter(),
        onset_octave_port=OnsetPitchOctaveNormalizeAdapter(),
        onset_normalize_port=OnsetNormalizeAdapter(),
        onset_frame_fuse_port=OnsetFrameFuseAdapter(),
        root_tab_build_port=RootTabBuildAdapter(),
        bass_tab_candidate_builder_port=candidate_builder,
        bass_tab_viterbi_port=viterbi,
        original_tab_generate_port=original_tab_generator,
        root_tab_generate_adapter=root_tab_generator,
    )

def build_request_from_job(job: MLJob) -> MLProcessRequestDTO:
    # Redis에서 가져온 값 그대로 사용 (없을 경우 대비해 기본값 처리)
    input_url = getattr(job, "input_wav_path", None)
    output_dir = getattr(job, "result_path", None) or getattr(job, "output_dir", "")

    if not input_url:
        logger.error(f"❌ [ERROR] Job 객체 내에 input_wav_path가 없습니다! job_id: {job.job_id}")

    logger.info(f"🔗 [CHECK] 최종 다운로드 주소: {input_url}")

    return MLProcessRequestDTO(
        job_id=job.job_id,
        song_id=job.song_id,
        result_id=job.result_id,
        input_wav_path=str(input_url),
        result_path=str(output_dir),
        norm_title=job.norm_title,
        norm_artist=job.norm_artist,
    )

async def process_one_job(
    *,
    job_id: str,
    store: RedisJobStore,
    usecase: RunMLProcessUseCase,
    cfg: MLWorkerConfig,
) -> None:
    # 1. Redis에서 상세 정보 가져오기 (prefix가 bass:ml:job: 이므로 정확히 찾아옴)
    job: MLJob | None = await store.get(job_id)
    
    if job is None:
        logger.warning("skip: job not found job_id=%s (키 확인 필요: bass:ml:job:%s)", job_id, job_id)
        return

    # 워커가 SUBMITTED 상태로 던지므로, 상태 체크 로직 완화 또는 수정
    try:
        request: MLProcessRequestDTO = build_request_from_job(job)

        if not request.input_wav_path or request.input_wav_path == "None":
            raise ValueError(f"input_wav_path가 비어있습니다. job_id: {job_id}")

        logger.info("🚀 ML 분석 시작 job_id=%s", job.job_id)
        response = await usecase.execute(request=request)
        logger.info("✅ ML 분석 완료 job_id=%s status=%s", response.job_id, response.status)

    except Exception as e:
        logger.exception("❌ ML 처리 중 에러 발생 job_id=%s error=%s", job_id, e)
        # 실패 상태 저장 (필요 시)
        try:
            job.mark_failed(error=str(e))
            await store.save(job, ttl_seconds=cfg.job_ttl_seconds)
        except:
            pass

async def worker_loop(cfg: MLWorkerConfig) -> None:
    r: redis.Redis = redis.from_url(cfg.redis_url, decode_responses=True)
    await r.ping()

    # ⭐ [중요] Store 생성 시 prefix를 워커의 저장 위치와 맞춤
    store: RedisJobStore = RedisJobStore(r, key_prefix=cfg.key_prefix)
    usecase: RunMLProcessUseCase = build_usecase(store=store)

    shutdown: GracefulShutdown = GracefulShutdown()
    shutdown.install()

    # 큐 이름 조립 확인 (워커가 bass:queue:process 에 넣으므로)
    # RedisJobStore.dequeue 내부에서 f"{key_prefix}queue:{queue_name}" 형태라면 조절 필요
    # 여기서는 store.dequeue("process") 호출 시 "bass:ml:job:queue:process"가 되지 않도록 주의
    
    logger.info("🔍 ML Worker 시작. 모니터링 큐: bass:queue:%s", cfg.queue_name)

    try:
        while not shutdown.stop_event.is_set():
            # 큐는 별도의 Prefix를 쓰거나 직접 접근
            # 워커가 던진 큐 위치: bass:queue:process
            raw_jid = await r.blpop("bass:queue:process", timeout=3)
            if raw_jid:
                job_id = raw_jid[1]
                logger.info("📥 [Dequeued] job_id=%s", job_id)
                await process_one_job(
                    job_id=job_id,
                    store=store,
                    usecase=usecase,
                    cfg=cfg,
                )
    finally:
        await r.aclose()

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 환경변수에서 설정을 가져오되, 워커의 저장 규칙을 최우선으로 함
    cfg = MLWorkerConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        key_prefix="bass:ml:", # 👈 워커가 저장하는 Prefix와 완전 일치
        queue_name="process",
    )

    asyncio.run(worker_loop(cfg))

if __name__ == "__main__":
    main()