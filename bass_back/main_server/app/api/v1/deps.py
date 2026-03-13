# main_server/app/api/v1/deps.py
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from redis.asyncio import Redis

from app.infra.redis import get_redis

from app.adapters.jobs.job_store_redis import RedisJobStore

from app.application.ports.job_store_port import JobStore
from app.application.ports.song_repository_port import SongRepositoryPort
from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.application.ports.asset_repository_port import AssetRepositoryPort

from app.adapters.songs.song_repository_adapter import SongRepositorySqliteAdapter
from app.adapters.songs.result_repository_adapter import ResultRepositorySqliteAdapter
from app.adapters.songs.asset_repository_adapter import AssetRepositorySqliteAdapter

from app.application.usecases.job.create_job_usecase import CreateJobUseCase
from app.application.usecases.RequestCreateJobUseCase import RequestCreateJobUseCase
from app.application.usecases.songs.song_create_usecase import CreateSongUseCase
from app.application.usecases.songs.result_create_usecase import CreateResultUseCase
from app.application.usecases.songs.song_search_usecase import SearchSongsUseCase


# ------------------------------------------------------------
# 경로지정
# ------------------------------------------------------------
@lru_cache
def get_paths() -> dict[str, Path]:
    """
    실행 위치가 어디든 흔들리지 않는 경로 결정
    """
    base_dir: Path = Path(__file__).resolve().parents[2]  # .../main_server/app
    project_dir: Path = base_dir.parent  # .../main_server

    var_dir: Path = project_dir / "var"
    var_dir.mkdir(parents=True, exist_ok=True)

    db_path: Path = var_dir / "index.db"

    return {
        "project_dir": project_dir,
        "var_dir": var_dir,
        "db_path": db_path,
    }


@lru_cache
def get_db_path() -> str:
    paths: dict[str, Path] = get_paths()
    return str(paths["db_path"])


# ------------------------------------------------------------
# 레디스관련
# ------------------------------------------------------------
@lru_cache
def get_redis_client() -> Redis:
    return get_redis()


@lru_cache
def get_job_store() -> JobStore:
    return RedisJobStore(
        redis=get_redis_client(),
        key_prefix="bass:",
    )


# ------------------------------------------------------------
# 포트에 어댑터 주입
# ------------------------------------------------------------
@lru_cache
def get_song_repo() -> SongRepositoryPort:
    return SongRepositorySqliteAdapter(
        db_path=get_db_path(),
    )


@lru_cache
def get_result_repo() -> ResultRepositoryPort:
    return ResultRepositorySqliteAdapter(
        db_path=get_db_path(),
    )


@lru_cache
def get_asset_repo() -> AssetRepositoryPort:
    return AssetRepositorySqliteAdapter(
        db_path=get_db_path(),
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
# Job UseCases
# ------------------------------------------------------------
@lru_cache
def get_create_job_uc() -> CreateJobUseCase:
    return CreateJobUseCase(
        job_store=get_job_store(),
        queue_name="youtube",
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