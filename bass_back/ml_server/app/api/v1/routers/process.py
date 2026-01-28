# ml_server/app/api/v1/routers/process.py
from __future__ import annotations

from typing import Any, Literal, Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["ml"])

class NoteEventDTO(BaseModel):
    pitch: int
    start_sec: float
    end_sec: float
    velocity: float = Field(ge=0.0, le=1.0)


class TabEventDTO(BaseModel):
    string: int = Field(ge=1, le=4)
    fret: int = Field(ge=0, le=24)
    start_sec: float
    end_sec: float
    confidence: float = Field(ge=0.0, le=1.0)

# 묶인 노트이벤트 dto와 탭 dto를 기반으로 결과들을 묶음
class ProcessResultDTO(BaseModel):
    bass_wav_path: Optional[str] = None
    notes: Optional[List[NoteEventDTO]] = None
    bpm: Optional[float] = None
    tabs: Optional[List[TabEventDTO]] = None
    meta: dict[str, Any] = Field(default_factory=dict)

# 묶은 최종 결과물과 성공, 모드를 묶음
class ProcessResponseDTO(BaseModel):
    ok: bool
    mode: Literal["original", "root"]
    result: Optional[ProcessResultDTO] = None
    error: Optional[str] = None

"""
    최종적으로 나가는 정보
    업로드파일
    job_id 
    onset 최소 
    frame 최소
    노트최소길이
 """
@router.post(
    "/process",
    response_model=ProcessResponseDTO,
    status_code=status.HTTP_200_OK,
)


async def process_audio(
    file: UploadFile = File(...),
    job_id: str = Form(...),
    mode: Literal["original", "root"] = Form("original"),
    onset_threshold: float = Form(0.5),
    frame_threshold: float = Form(0.3),
    min_note_len_ms: float = Form(127.7),
):
    try:
        result = ProcessResultDTO(
            meta={"filename": file.filename}
        )

        return ProcessResponseDTO(
            ok=True,
            mode=mode,
            result=result,
        )

    except ValueError as e:
        # 입력/옵션 오류
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except Exception as e:
        # 처리 중 내부 오류
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ML processing failed",
        )
