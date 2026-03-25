from __future__ import annotations
import os
import io
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from redis.asyncio import Redis
from supabase import create_client, Client
from dotenv import load_dotenv
from pydantic import BaseModel
from pydub import AudioSegment 

from app.domain.jobs_domain import JobStatus
from app.domain.errors_domain import JobNotFoundError
from app.application.usecases.RequestCreateJobUseCase import RequestCreateJobUseCase
from app.application.usecases.job.get_job_usecase import GetJobUseCase
from app.application.usecases.songs.song_create_usecase import CreateSongUseCase
from app.application.usecases.songs.result_create_usecase import CreateResultUseCase
from app.infra.redis import get_redis
from app.api.v1.deps import (
    get_request_create_job_uc, 
    get_get_job_uc, 
    get_create_song_uc, 
    get_create_result_uc
)
from app.api.v1.dto.results_dto import CreateResultResponse

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

router = APIRouter(prefix="/jobs", tags=["jobs"])

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    youtube_url: str | None = None
    title: str | None = None
    artist: str | None = None
    error: str | None = None

@router.post("/upload", response_model=CreateResultResponse, status_code=status.HTTP_201_CREATED)
async def create_upload_job(
    title: str = Form(...),
    artist: str = Form(...),
    file: UploadFile = File(...),
    redis: Redis = Depends(get_redis),
    job_uc: RequestCreateJobUseCase = Depends(get_request_create_job_uc),
    song_uc: CreateSongUseCase = Depends(get_create_song_uc),
    result_uc: CreateResultUseCase = Depends(get_create_result_uc),
) -> CreateResultResponse:
    
    # 1. Song & Job 생성
    song = await song_uc.execute(title=title, artist=artist)
    job = await job_uc.execute(youtube_url="MANUAL_UPLOAD", title=title, artist=artist)
    
    # 2. 파일 데이터 읽기
    await file.seek(0)
    input_data = await file.read()
    
    # 3. [핵심] WAV -> MP3 변환 (메모리 내 작업)
    try:
        print(f"🔄 변환 시작: {len(input_data)} bytes (WAV)")
        
        # 바이너리 데이터를 오디오 객체로 로드
        audio = AudioSegment.from_file(io.BytesIO(input_data))
        
        # MP3로 변환하여 메모리 버퍼(BytesIO)에 담기
        mp3_buffer = io.BytesIO()
        audio.export(mp3_buffer, format="mp3", bitrate="192k") # 192kbps면 음질 충분해!
        mp3_data = mp3_buffer.getvalue()
        
        print(f"✅ 변환 완료: {len(mp3_data)} bytes (MP3)")
    except Exception as e:
        print(f"❌ 변환 실패: {e}")
        raise HTTPException(status_code=500, detail="오디오 변환 중 오류 발생")

    # 4. Supabase Storage 업로드 (경로 확장자를 .mp3로 변경)
    storage_path = f"results/{job.result_id}/audio/original.mp3"
    
    try:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=storage_path,
            file=mp3_data,
            file_options={"content-type": "audio/mpeg", "upsert": "true"}
        )
        file_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(storage_path)
    except Exception as e:
        print(f"❌ Supabase 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail="저장소 업로드 실패")

    # 5. Result 생성 및 큐 등록
    result = await result_uc.execute(
        result_id=job.result_id, 
        song_id=song.song_id, 
        source_url=file_url 
    )    
    await redis.lpush("ml:queue:process", job.job_id)
    
    return CreateResultResponse(result_id=job.result_id, song_id=song.song_id)

# (조회 엔드포인트는 기존과 동일)
# --- 조회 엔드포인트 ---
@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    uc: GetJobUseCase = Depends(get_get_job_uc),
) -> JobResponse:
    try:
        job = await uc.execute(job_id=job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        youtube_url=job.youtube_url,
        title=job.title,
        artist=job.artist,
        error=job.error,
    )