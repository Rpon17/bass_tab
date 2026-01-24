# main_server/app/adapters/ml/http_client.py
from __future__ import annotations

from pathlib import Path
import httpx

from app.adapters.ml.dto import (
    MLProcessRequestDTO,
    MLProcessResponseDTO,
)

"""
    역할:
    실제로 요청하는 코드
    결과파일이 들어오면 이걸 json형식으로 return 함
"""

# base_url로 들어온 코드에서 끝의 / 를 없앤다 나중에 사용시 //를 함을 막아쥼
# timeout 시간을 120초로 정함 이거 넘으면 안되는거
class MLServerHttpClient:
    def __init__(self, base_url: str, *, timeout_sec: float = 120.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_sec

    # 요청 dto를 넣으면 수신 dto를 받는 과정
    # 파일 유무 검사하고 구체적인 데이터들을 집어넣음
    async def process(self, req: MLProcessRequestDTO) -> MLProcessResponseDTO:
        wav_path = Path(req.file_path)
        if not wav_path.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_path}")

        url = f"{self._base_url}/v1/process"

        data = {
            "job_id": req.job_id,
            "mode": req.form.mode,
            "onset_threshold": str(req.form.onset_threshold),
            "frame_threshold": str(req.form.frame_threshold),
            "min_note_len_ms": str(req.form.min_note_len_ms),
        }

        # wav경로를 염 그리고 그 이름대로 확인하고
        # json형태로 return 해줌
        with wav_path.open("rb") as f:
            files = {"file": (wav_path.name, f, "audio/wav")}
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, data=data, files=files)
                resp.raise_for_status()
                return MLProcessResponseDTO.model_validate(resp.json())
