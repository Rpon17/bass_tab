from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path

# 환경 변수 로드를 위해 추가
from dotenv import load_dotenv
from redis.asyncio import Redis, from_url 

# .env 파일 읽기
load_dotenv()

# 어댑터 및 포트 임포트
from app.adapters.jobs.job_store_redis import RedisJobStore
from app.application.ports.job_store_port import JobStore
from app.application.ports.front_back_port import FrontBackRepositoryPort
from app.application.ports.song_repository_port import SongRepositoryPort
from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.application.ports.asset_repository_port import AssetRepositoryPort

# ✅ Postgres 어댑터들
from app.adapters.front_back_adapter import FrontBackPostgresAdapter
from app.adapters.songs.song_repository_adapter import SongRepositoryPostgresAdapter
from app.adapters.songs.result_repository_adapter import ResultRepositoryPostgresAdapter
from app.adapters.songs.asset_repository_adapter import AssetRepositoryPostgresAdapter

# 유스케이스들
from app.application.usecases.front_back_usecase import FrontBackUsecase 
from app.application.usecases.job.create_job_usecase import CreateJobUseCase
from app.application.usecases.job.get_job_usecase import GetJobUseCase
from app.application.usecases.RequestCreateJobUseCase import RequestCreateJobUseCase
from app.application.usecases.songs.song_create_usecase import CreateSongUseCase
from app.application.usecases.songs.result_create_usecase import CreateResultUseCase
from app.application.usecases.songs.asset_create_usecase import CreateAssetUseCase
from app.application.usecases.songs.song_search_usecase import SearchSongsUseCase
from app.application.usecases.songs.get_results_by_song_usecase import GetResultsBySongUseCase

# ------------------------------------------------------------
# 1. 환경 설정 및 주소 관리
# ------------------------------------------------------------
@lru_cache
def get_db_url() -> str:
    # 💡 Render/Supabase 연결을 위해 postgres:// 를 postgresql:// 로 자동 변환
    url = os.getenv("DATABASE_URL", "sqlite:///./index.db")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

@lru_cache
def get_api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://localhost:8000")

# ------------------------------------------------------------
# 레디스 관련
# ------------------------------------------------------------
@lru_cache
def get_redis_client() -> Redis:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return from_url(redis_url, decode_responses=True)

@lru_cache
def get_job_store() -> JobStore:
    return RedisJobStore(
        redis=get_redis_client(),
        key_prefix="bass:",
    )

# ------------------------------------------------------------
# ✅ 포트에 어댑터 주입 (매개변수명을 db_url로 일치시킴)
# ------------------------------------------------------------
@lru_cache
def get_song_repo() -> SongRepositoryPort:
    return SongRepositoryPostgresAdapter(
        db_url=get_db_url(), # 👈 db_path에서 db_url로 수정
    )

@lru_cache
def get_result_repo() -> ResultRepositoryPort:
    return ResultRepositoryPostgresAdapter(
        db_url=get_db_url(), # 👈 db_path에서 db_url로 수정
    )

@lru_cache
def get_asset_repo() -> AssetRepositoryPort:
    return AssetRepositoryPostgresAdapter(
        db_url=get_db_url(), # 👈 db_path에서 db_url로 수정
    )
    
@lru_cache
def get_front_back_adapter() -> FrontBackRepositoryPort:
    return FrontBackPostgresAdapter(
        db_url=get_db_url(), # 👈 db_path에서 db_url로 수정
    )

# ------------------------------------------------------------
# 이후 UseCase 생성 함수들은 기존과 동일 (생략 없이 그대로 사용하면 됨)
# ------------------------------------------------------------
@lru_cache
def get_create_song_uc() -> CreateSongUseCase:
    return CreateSongUseCase(song_repository=get_song_repo())

@lru_cache
def get_search_songs_uc() -> SearchSongsUseCase:
    return SearchSongsUseCase(song_repository=get_song_repo())

@lru_cache
def get_create_result_uc() -> CreateResultUseCase:
    return CreateResultUseCase(result_repository=get_result_repo())
    
@lru_cache
def get_create_asset_uc() -> CreateAssetUseCase:
    return CreateAssetUseCase(asset_repository=get_asset_repo())
    
@lru_cache
def get_create_job_uc() -> CreateJobUseCase:
    return CreateJobUseCase(job_store=get_job_store(), queue_name="youtube")

@lru_cache
def get_get_job_uc() -> GetJobUseCase:
    return GetJobUseCase(job_store=get_job_store())

@lru_cache
def get_request_create_job_uc() -> RequestCreateJobUseCase:
    return RequestCreateJobUseCase(
        create_song_uc=get_create_song_uc(),
        create_result_uc=get_create_result_uc(),
        create_job_uc=get_create_job_uc(),
    )
    
@lru_cache
def get_get_results_by_song_uc() -> GetResultsBySongUseCase:
    return GetResultsBySongUseCase(result_repository=get_result_repo())

@lru_cache
def get_front_back_uc() -> FrontBackUsecase:
    adapter = get_front_back_adapter()
    return FrontBackUsecase(
        repository=adapter,
        base_url=get_api_base_url() 
    )