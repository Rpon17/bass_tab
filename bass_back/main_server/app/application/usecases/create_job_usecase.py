# main_server/app/application/usecases/enqueue_job.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Dict, Any, Optional

from bass_back.main_server.app.domain.jobs_domain import Job
from bass_back.main_server.app.application.ports.job_store_port import JobStore

""" 
    job을 만드는 코드 job_id가 만들어지며 
    그 job_id를 토대로 레포지토리에 job이 하나 저장된다
    결과적으로 job_id를 return 한다
"""
@dataclass(frozen=True)
class CreateJobUseCase:
    job_store: JobStore

    async def execute(
        self,
        *,
        youtube_url: str,
        ttl_seconds: int = 60 * 30,
    ) -> str:
        job_id = uuid.uuid4().hex
        # 여기서는 job이라는 도메인 객체를 하나 생성한다 '선언'
        job = Job.create(job_id=job_id)

        # 방금 만든 Job 객체를 외부 저장소(Redis, DB 등)에 실제로 저장 '전달'
        # create(job)는 “조회/상태관리용 저장”
        await self.job_store.create(job, ttl_seconds=ttl_seconds)
        # enqueue(queue, job_id)는 “실행 트리거(처리 대상 목록)
        await self.job_store.enqueue("youtube", job.job_id)
        return job_id

