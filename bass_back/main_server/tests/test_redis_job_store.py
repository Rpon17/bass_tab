import asyncio
import pytest
from datetime import datetime

from redis.asyncio import Redis

from app.adapters.jobs.job_store_redis import RedisJobStore
from bass_back.main_server.app.domain.jobs_domain import Job, JobStatus


@pytest.mark.asyncio
async def test_save_and_get_job():
    # 1. Redis 연결
    redis = Redis(host="localhost", port=6379, db=0, decode_responses=True)

    store = RedisJobStore(
        redis,
        key_prefix="test:job",
    )

    # 2. 테스트용 Job 생성
    job = Job(
        job_id="job-test-001",
        status=JobStatus.QUEUED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        input_wav_path="input.wav",
    )

    # 3. 저장
    await store.save(job, ttl_seconds=60)

    # 4. 다시 조회
    loaded = await store.get(job.job_id)

    # 5. 검증
    assert loaded is not None
    assert loaded.job_id == job.job_id
    assert loaded.status == JobStatus.QUEUED
    assert loaded.input_wav_path == "input.wav"

    # 6. TTL 확인 (선택)
    ttl = await redis.ttl(store._job_key(job.job_id))
    assert ttl > 0

    await redis.close()
