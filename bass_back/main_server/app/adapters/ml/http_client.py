from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.application.ports.ml_client_port import (
    MLClientPort,
    MLProcessResponse,
)


@dataclass(frozen=True)
class HttpMLClient(MLClientPort):
    base_url: str
    timeout_seconds: float = 120.0

    async def process(
        self,
        *,
        job_id: str,
        song_id: str,
        result_id: str,
        input_wav_path: str,
        result_path: str,
        norm_title: Optional[str] = None,
        norm_artist: Optional[str] = None,
    ) -> MLProcessResponse:
        payload: dict[str, object] = {
            "job_id": job_id,
            "song_id": song_id,
            "result_id": result_id,
            "input_wav_path": input_wav_path,
            "result_path": result_path,
            "norm_title": norm_title,
            "norm_artist": norm_artist,
        }

        url: str = f"{self.base_url}/v1/process"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                r: httpx.Response = await client.post(url, json=payload)
                r.raise_for_status()
                data: dict[str, object] = r.json()

        except httpx.TimeoutException as e:
            return MLProcessResponse(
                ok=False,
                job_id=job_id,
                song_id=song_id,
                result_id=result_id,
                asset_id=None,
                status="failed",
                path=None,
                error=f"ML timeout: {e}",
            )
        except httpx.HTTPError as e:
            return MLProcessResponse(
                ok=False,
                job_id=job_id,
                song_id=song_id,
                result_id=result_id,
                asset_id=None,
                status="failed",
                path=None,
                error=f"ML http error: {e}",
            )
        except Exception as e:
            return MLProcessResponse(
                ok=False,
                job_id=job_id,
                song_id=song_id,
                result_id=result_id,
                asset_id=None,
                status="failed",
                path=None,
                error=f"ML unknown error: {e}",
            )

        response_error: Optional[str] = None
        raw_error: object = data.get("error")
        if raw_error is not None:
            response_error = str(raw_error)

        response_job_id: str = str(data.get("job_id") or job_id)
        response_song_id: str = str(data.get("song_id") or song_id)
        response_result_id: str = str(data.get("result_id") or result_id)

        raw_asset_id: object = data.get("asset_id")
        response_asset_id: Optional[str] = None if raw_asset_id in (None, "") else str(raw_asset_id)

        raw_status: object = data.get("status")
        response_status: str = str(raw_status or "queued")

        raw_path: object = data.get("path")
        response_path: Optional[str] = None if raw_path in (None, "") else str(raw_path)

        return MLProcessResponse(
            ok=response_error is None,
            job_id=response_job_id,
            song_id=response_song_id,
            result_id=response_result_id,
            asset_id=response_asset_id,
            status=response_status,
            path=response_path,
            error=response_error,
        )