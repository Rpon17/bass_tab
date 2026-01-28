# worker/ml_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal

import httpx

Mode = Literal["separate", "analyze", "tab", "full"]

@dataclass(frozen=True)
class MLProcessResult:
    bass_wav_path: Optional[str] = None
    bpm: Optional[float] = None
    notes: Optional[list[dict]] = None
    tabs: Optional[list[dict]] = None

@dataclass(frozen=True)
class MLProcessResponse:
    ok: bool
    mode: Mode
    result: Optional[MLProcessResult] = None
    error: Optional[str] = None


class MLHttpClient:
    def __init__(self, *, base_url: str, timeout_sec: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_sec)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def process(
        self,
        *,
        job_id: str,
        input_wav_path: str,
        mode: Mode = "full",
        meta: Optional[Dict[str, Any]] = None,
    ) -> MLProcessResponse:
        payload = {
            "job_id": job_id,
            "input_wav_path": input_wav_path,
            "mode": mode,
            "meta": meta or {},
        }
        r = await self._client.post(f"{self._base_url}/v1/process", json=payload)
        r.raise_for_status()
        data = r.json()

        # data를 dataclass로 매핑 (방어적)
        result = data.get("result")
        parsed_result = None
        if isinstance(result, dict):
            parsed_result = MLProcessResult(
                bass_wav_path=result.get("bass_wav_path"),
                bpm=result.get("bpm"),
                notes=result.get("notes"),
                tabs=result.get("tabs"),
            )

        return MLProcessResponse(
            ok=bool(data.get("ok")),
            mode=data.get("mode", mode),
            result=parsed_result,
            error=data.get("error"),
        )
