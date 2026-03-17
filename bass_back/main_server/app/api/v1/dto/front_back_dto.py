# app/api/v1/schemas/song_response.py
from pydantic import BaseModel
from typing import Optional, Dict

class ResultDTO(BaseModel):
    result_id: str
    asset_id: str  # 추가: 실제 파일 세트의 고유 ID
    
    # 4가지 오디오 경로
    audio: Dict[str, str] = {
        "original": "",
        "bass_only": "",
        "bass_removed": "",
        "bass_boosted": ""
    }
    
    tab: Dict[str, str] = {
        "original": "",
        "root": ""
    }

class SongSearchResponse(BaseModel):
    song_id: str
    title: str
    artist: str
    result: Optional[ResultDTO] = None