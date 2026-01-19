# ml_server/app/api/v1/routers/process.py
from __future__ import annotations

from typing import Any, Literal, Optional, List
from fastapi import APIRouter, UploadFile, File, Form
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


class ProcessResultDTO(BaseModel):
    bass_wav_path: Optional[str] = None
    notes: Optional[List[NoteEventDTO]] = None
    bpm: Optional[float] = None
    tabs: Optional[List[TabEventDTO]] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ProcessResponseDTO(BaseModel):
    ok: bool
    mode: Literal["original", "root"]
    result: Optional[ProcessResultDTO] = None
    error: Optional[str] = None


@router.post("/process", response_model=ProcessResponseDTO)
async def process_audio(
    file: UploadFile = File(..., description="Input WAV file"),
    job_id: str = Form(..., description="Job identifier from main_server"),
    mode: Literal["original", "root"] = Form("original"),
    onset_threshold: float = Form(0.5),
    frame_threshold: float = Form(0.3),
    min_note_len_ms: float = Form(127.7),
):
    try:
        return ProcessResponseDTO(
            ok=True,
            job_id=job_id,
            mode=mode,
            result=ProcessResultDTO(meta={"filename": file.filename}),
        )
    except Exception as e:
        return ProcessResponseDTO(
            ok=False,
            job_id=job_id,
            mode=mode,
            error=str(e),
        )
