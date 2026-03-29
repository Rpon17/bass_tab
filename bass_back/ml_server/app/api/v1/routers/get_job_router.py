import os
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
import redis.asyncio as redis
from dotenv import load_dotenv

# 본인의 프로젝트 구조에 맞게 수정 (이 부분이 틀리면 임포트 에러가 날 수 있음)
from app.adapters.job.job_store_redis import RedisJobStore
from app.domain.models_domain import MLJob
from app.domain.jobs_domain import MLJobStatus
from shared.dtos.main_ml_dto import MLProcessRequestDTO, MLProcessResponseDTO

# 1. 환경 변수 로드
load_dotenv()

# 2. 라우터 및 로거 설정
router = APIRouter(prefix="/v1", tags=["ml-process"])
logger = logging.getLogger(__name__)

# 3. [핵심] get_redis 함수 정의 (라우터 메서드보다 위에 있어야 함)
async def get_redis() -> redis.Redis:
    """
    Redis 연결을 생성하고 반환하는 의존성 함수입니다.
    """
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    # decode_responses=True 설정을 해야 Redis에서 데이터를 읽을 때 
    # bytes가 아닌 문자열(str)로 바로 가져옵니다.
    return redis.from_url(redis_url, decode_responses=True)

# --- [디버깅용] GET Job 라우터 ---
@router.get("/job/{job_id}", response_model=MLProcessResponseDTO)
async def get_job_debug(
    job_id: str,
    r: redis.Redis = Depends(get_redis) # 위에서 정의한 get_redis를 사용
):
    job_prefix = os.getenv("ML_JOB_KEY_PREFIX", "bass:ml:")
    store = RedisJobStore(r, key_prefix=job_prefix)
    
    try:
        job = await store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found in Redis")

        # 서버 터미널(콘솔) 확인용 로그
        print("\n" + "🚀" * 10 + " DATA INSPECTION " + "🚀" * 10)
        print(f"ID: {job.job_id}")
        print(f"OUTPUT_DIR: '{job.output_dir}'")
        print(f"RESULT_PATH: '{job.result_path}'")
        print("🚀" * 30 + "\n")

        return job.to_public_payload()
        
    except Exception as e:
        logger.error(f"Error retrieving job: {e}")
        raise HTTPException(status_code=500, detail=str(e))