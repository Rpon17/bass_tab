# main_server/app/adapters/ml/dto.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class MLProcessFormDTO(BaseModel):
    """
    ML 처리 옵션 (의미 데이터)
    """
    mode: Literal["original", "root"] = "original"
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    min_note_len_ms: float = 127.7


class MLProcessRequestDTO(BaseModel):
    job_id: str                      
    file_path: str   
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
