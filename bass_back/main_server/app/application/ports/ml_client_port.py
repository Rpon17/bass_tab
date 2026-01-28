from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from app.domain.jobs_domain import SourceMode, ResultMode


# result 내용 정리 (notes/tabs는 일단 frame 기반 dict 리스트로 둠)
@dataclass(frozen=True)
class MLProcessResult:
    bass_wav_path: Optional[str] = None
    bpm: Optional[float] = None
    notes: Optional[list[dict]] = None
    tabs: Optional[list[dict]] = None


# ml_server에서 받아올 응답
@dataclass(frozen=True)
class MLProcessResponse:
    ok: bool
    source_mode: SourceMode
    result_mode: ResultMode
    result: Optional[MLProcessResult] = None
    error: Optional[str] = None


# ml_server에 요청을 보내는 포트
class MLClientPort(Protocol):
    async def process(
        self,
        *,
        job_id: str,
        input_wav_path: str,
        source_mode: SourceMode = SourceMode.ORIGINAL,
        result_mode: ResultMode = ResultMode.FULL,
        meta: Optional[Dict[str, Any]] = None,
    ) -> MLProcessResponse:
        ...
