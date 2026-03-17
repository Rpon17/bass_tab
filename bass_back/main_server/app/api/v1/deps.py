from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path

# 환경 변수 로드를 위해 추가
from dotenv import load_dotenv
from redis.asyncio import Redis, from_url # from_url 추가 (배포용)

# .env 파일 읽기
load_dotenv()

# infra/redis.py 대신 여기서 직접 생성하거나 infra 쪽을 수정해서 사용
from app.adapters.jobs.job_store_redis import RedisJobStore

from app.application.ports.job_store_port import JobStore
from app.application.ports.song_repository_port import SongRepositoryPort
from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.application.ports.asset_repository_port import AssetRepositoryPort

from app.adapters.front_back_adapter import FrontBackSqliteAdapter
from app.adapters.songs.song_repository_adapter import SongRepositorySqliteAdapter
from app.adapters.songs.result_repository_adapter import ResultRepositorySqliteAdapter
from app.adapters.songs.asset_repository_adapter import AssetRepositorySqliteAdapter

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
    return os.getenv("DATABASE_URL", "sqlite:///./index.db")

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
# 포트에 어댑터 주입 (환경 변수 적용)
# ------------------------------------------------------------
@lru_cache
def get_song_repo() -> SongRepositoryPort:
    return SongRepositorySqliteAdapter(
        db_path=get_db_url(),
    )


@lru_cache
def get_result_repo() -> ResultRepositoryPort:
    return ResultRepositorySqliteAdapter(
        db_path=get_db_url(),
    )


@lru_cache
def get_asset_repo() -> AssetRepositoryPort:
    return AssetRepositorySqliteAdapter(
        db_path=get_db_url(),
    )
    
@lru_cache
def get_front_back_adapter() -> FrontBackSqliteAdapter:
    return FrontBackSqliteAdapter(
        db_path=get_db_url(), 
    )

# ------------------------------------------------------------
# song_usecase
# ------------------------------------------------------------
@lru_cache
def get_create_song_uc() -> CreateSongUseCase:
    return CreateSongUseCase(
        song_repository=get_song_repo(),
    )


@lru_cache
def get_search_songs_uc() -> SearchSongsUseCase:
    return SearchSongsUseCase(
        song_repository=get_song_repo(),
    )


# ------------------------------------------------------------
# Result UseCases
# ------------------------------------------------------------
@lru_cache
def get_create_result_uc() -> CreateResultUseCase:
    return CreateResultUseCase(
        result_repository=get_result_repo(),
    )
    
    
# ------------------------------------------------------------
# Asset UseCases
# ------------------------------------------------------------
@lru_cache
def get_create_asset_uc() -> CreateAssetUseCase:
    return CreateAssetUseCase(
        asset_repository=get_asset_repo(),
    )
    

# ------------------------------------------------------------
# Job UseCases
# ------------------------------------------------------------
@lru_cache
def get_create_job_uc() -> CreateJobUseCase:
    return CreateJobUseCase(
        job_store=get_job_store(),
        queue_name="youtube",
    )


@lru_cache
def get_get_job_uc() -> GetJobUseCase:
    return GetJobUseCase(
        job_store=get_job_store(),
    )


# ------------------------------------------------------------
# Orchestration UseCases
# ------------------------------------------------------------
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