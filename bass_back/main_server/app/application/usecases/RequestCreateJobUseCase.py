# main_server/app/application/usecases/request_create_job_usecase.py
from __future__ import annotations

from dataclasses import dataclass

from app.domain.jobs_domain import Job
from app.domain.songs_domain import Song
from app.application.usecases.job.create_job_usecase import CreateJobUseCase
from app.application.usecases.songs.song_create_usecase import CreateSongUseCase


@dataclass(frozen=True)
class RequestCreateJobUseCase:
    """
    Orchestrator UseCase.

    - CreateSongUseCase: (title, artist)로 Song get-or-create
    - CreateJobUseCase:  Song.song_id를 사용해 Job 생성 + enqueue

    라우터는 이 UseCase만 호출하면 됨.
    """
    create_song_uc: CreateSongUseCase
    create_job_uc: CreateJobUseCase

    async def execute(
        self,
        *,
        youtube_url: str,
        title: str,
        artist: str,
        ttl_seconds: int = 60 * 30,
    ) -> Job:
        # 1) song get-or-create
        song = await self.create_song_uc.execute(
            title=title,
            artist=artist,
        )

        # 2) job 생성 (반드시 song_id는 song에서 가져옴)
        job = await self.create_job_uc.execute(
            youtube_url=youtube_url,
            title=song.title,
            artist=song.artist,
            song_id=song.song_id,
            ttl_seconds=ttl_seconds,
        )

        return job
