# main_server/app/application/usecases/enqueue_job.py
from __future__ import annotations

import uuid
from dataclasses import dataclass

from redis.asyncio import Redis

from app.domain.jobs_domain import Job
from app.application.ports.job_store_port import JobStore


@dataclass(frozen=True)
class CreateJobUseCase:
    job_store: JobStore
    queue_name: str = "youtube"
    debug_redis: Redis | None = None

    async def execute(
        self,
        *,
        youtube_url: str,
        title: str,
        artist: str,
        song_id: str,
        ttl_seconds: int = 60 * 30,
    ) -> Job:

        job_id: str = uuid.uuid4().hex
        result_id: str = uuid.uuid4().hex

        job: Job = Job.create(
            job_id=job_id,
            result_id=result_id,
            song_id=song_id,
            youtube_url=youtube_url,
            title=title,
            artist=artist,
        )

        await self.job_store.create(job, ttl_seconds=ttl_seconds)

        await self.job_store.enqueue(self.queue_name, job.job_id)

        if self.debug_redis is not None:
            await self.debug_redis.set("debug:main_server_alive", "1", ex=60)

        return job