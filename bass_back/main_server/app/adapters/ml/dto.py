# main_server/app/adapters/ml/dto.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class MLProcessFormDTO(BaseModel):
    """
    ! 외부계약 이므로 adapter에 둠 !
    역할 : 
    ML서버에 어떤것을 요청할지 정리하고
        요청사항
        job_id , file_path, form 형태
        
        
    ML서버에서 수신을 어떻게 받을지 정리함
        수신사항
        ok , job_id, mode, result 혹은 error
    """
    mode: Literal["original", "root"] = "original"
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    min_note_len_ms: float = 127.7

# 요청하는 dto 
class MLProcessRequestDTO(BaseModel):
    job_id: str                      
    file_path: str   
    # 요청이 올때마다 MLProcessFormDTO()을 새로 만듬
    form: MLProcessFormDTO = Field(default_factory=MLProcessFormDTO)

# dto 수신파트
class MLNoteEventDTO(BaseModel):
    pitch: int
    start_sec: float
    end_sec: float
    velocity: float


class MLTabEventDTO(BaseModel):
    string: int
    fret: int
    start_sec: float
    end_sec: float
    confidence: float


class MLProcessResultDTO(BaseModel):
    bass_wav_path: Optional[str] = None
    notes: Optional[List[MLNoteEventDTO]] = None
    bpm: Optional[float] = None
    tabs: Optional[List[MLTabEventDTO]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class MLProcessResponseDTO(BaseModel):
    """
    ml_server → main_server 응답
    """
    ok: bool
    job_id: str                        
    mode: Literal["original", "root"]
    result: Optional[MLProcessResultDTO] = None
    error: Optional[str] = None
