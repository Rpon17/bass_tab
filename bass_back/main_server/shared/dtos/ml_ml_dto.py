from __future__ import annotations

from pydantic import BaseModel
from typing import Optional

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