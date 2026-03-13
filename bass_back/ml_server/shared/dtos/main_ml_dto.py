from __future__ import annotations

from pydantic import BaseModel
from typing import Optional

# result_path는 storage_root/song/song_id/result/result_id 이고
# 실제로 original.wav 다운로드 하는 경로도 storage_root/song/song_id/result/result_id/audio/original.wav
# 이므로 옮겨줘야 한다
# ml_server에서 audio와 tab을 나눠서 저장하자

class MLProcessRequestDTO(BaseModel):
    job_id: str
    song_id: str
    result_id: str
    input_wav_path: str
    result_path: str
    norm_title: Optional[str] = None
    norm_artist: Optional[str] = None

class MLProcessResponseDTO(BaseModel): 
    job_id: str
    song_id: str
    result_id: str
    asset_id: str
    status: str 
    path : str
    error: str | None = None
