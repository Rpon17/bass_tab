from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal
import httpx

from app.application.ports.ml_client_port import (
    MLClientPort, MLProcessResponse, MLProcessResult, Mode
)

@dataclass(frozen=True)
class HttpMLClient(MLClientPort):
    base_url: str
    timeout_seconds: float = 120.0

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
            "mode": mode,
            "input_wav_path": input_wav_path,
            "meta": meta or {},
        }

        url = f"{self.base_url}/v1/process"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
        except (httpx.TimeoutException) as e:
            return MLProcessResponse(ok=False, mode=mode, error=f"ML timeout: {e}")
        except (httpx.HTTPError) as e:
            return MLProcessResponse(ok=False, mode=mode, error=f"ML http error: {e}")
        except Exception as e:
            return MLProcessResponse(ok=False, mode=mode, error=f"ML unknown error: {e}")

        # ML 서버 DTO를 main_server 내부 모델로 매핑
        if not data.get("ok"):
            return MLProcessResponse(ok=False, mode=data.get("mode", mode), error=data.get("error"))

        result = data.get("result") or {}
        return MLProcessResponse(
            ok=True,
            mode=data.get("mode", mode),
            result=MLProcessResult(
                bass_wav_path=result.get("bass_wav_path"),
                bpm=result.get("bpm"),
                notes=result.get("notes"),
                tabs=result.get("tabs"),
            ),
            error=None,
        )
