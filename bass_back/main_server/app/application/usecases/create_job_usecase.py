# main_server/app/application/usecases/enqueue_job.py
from __future__ import annotations

import uuid
from dataclasses import dataclass

from bass_back.main_server.app.domain.jobs_domain import Job , SourceMode, ResultMode
from bass_back.main_server.app.application.ports.job_store_port import JobStore

@dataclass(frozen=True)
class CreateJobUseCase:
    job_store: JobStore

    async def execute(
        self,
        *,
        youtube_url: str,
        source_mode : SourceMode = SourceMode.ORIGINAL,
        result_mode : ResultMode = ResultMode.FULL,
        ttl_seconds: int = 60 * 30,
    ) -> Job:
        job_id = uuid.uuid4().hex

        # 도메인 Job 생성 (youtube_url 포함)
        job = Job.create(job_id=job_id, youtube_url=youtube_url, source_mode=source_mode, result_mode=result_mode)
        
        # 저장(조회/상태관리용)
        await self.job_store.create(job, ttl_seconds=ttl_seconds)

        # ✅ 큐잉(워커가 처리할 대상 목록)
        await self.job_store.enqueue("youtube", job.job_id)

        # ✅ Job 객체 반환
        return job
