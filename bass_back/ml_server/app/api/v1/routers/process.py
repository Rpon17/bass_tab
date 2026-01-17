# ml_server/app/api/v1/routers/process.py
from __future__ import annotations

from typing import Any, Literal, Optional, List
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel, Field

# 이제 모든 라우터는 v1아래에 m1이라는 이름으로 붙음
router = APIRouter(prefix="/v1", tags=["ml"])


# ---------
# 서버끼리, 레이어끼리 주고받기로 약속한 데이터 봉투
# ---------

# analyze의 처리결과를 담음 형태는 list안의 객체지만 나갈떄는 json형태로 나감
class NoteEventDTO(BaseModel):
    pitch: int
    start_sec: float
    end_sec: float
    velocity: float = Field(ge=0.0, le=1.0)

# tab의 처리결과를 담음 형태는 list안의 객체지만 나갈떄는 json형태로 나감
class TabEventDTO(BaseModel):
    string: int = Field(ge=1, le=4)  # 4-string bass 기준
    fret: int = Field(ge=0, le=24)
    start_sec: float
    end_sec: float
    confidence: float = Field(ge=0.0, le=1.0)

# ml서버의 처리결과의 묶음을 담음 형태는 list안의 객체지만 나갈떄는 json형태로 나감
class ProcessResultDTO(BaseModel):
    # seperate 결과
    bass_wav_path: Optional[str] = None          
    # notes에 값이 들어온다면 그 값은 리스트여야 하고 리스트 안의 각 원소는 NoteEventDTO 타입이어야 한다
    notes: Optional[List[NoteEventDTO]] = None  
    bpm: Optional[float] = None                  # optional
    # tabs 에 값이 들어온다면 그 값은 리스트여야 하고 리스트 안의 각 원소는 TabEventDTO 타입이어야 한다.
    tabs: Optional[List[TabEventDTO]] = None     # tab/full 결과
    # 딕셔너리여야 하지만 아무거나 와도 됨 {"model": "basic-pitch-v1"} 이런식임
    meta: dict[str, Any] = Field(default_factory=dict)


# ML서버의 성공 실패자체를 관장함
class ProcessResponseDTO(BaseModel):
    ok: bool
    mode: Literal["separate", "analyze", "tab", "full"]
    result: Optional[ProcessResultDTO] = None
    error: Optional[str] = None


# ---------
# Endpoint
# ---------
@router.post(
    "/process",
    response_model=ProcessResponseDTO,
)
async def process_audio(
    # 파일 업로드
    file: UploadFile = File(..., description="Input WAV file"),
    # 처리 모드
    mode: Literal["separate", "analyze", "tab", "full"] = Form("full"),
    # 옵션들 (필요한 것만 먼저 고정)
    onset_threshold: float = Form(0.5),
    frame_threshold: float = Form(0.3),
    min_note_len_ms: float = Form(127.7),
):
    """
    ML server: wav 입력 -> (separate/analyze/tab/full) 처리 -> JSON 결과 반환
    지금은 DTO/스키마 고정이 목적이므로 내부 구현은 더미여도 됨.
    """
    try:
        # TODO: 임시 - 나중에 실제 처리 로직 연결
        # file.file: SpooledTemporaryFile. 필요 시 /tmp에 저장 후 처리.
        return ProcessResponseDTO(ok=True, mode=mode, result=ProcessResultDTO(meta={"filename": file.filename}))
    except Exception as e:
        return ProcessResponseDTO(ok=False, mode=mode, error=str(e))
