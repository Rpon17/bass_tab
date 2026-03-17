from __future__ import annotations

from pydantic import BaseModel
from pathlib import Path

# ml_server로 저장할 dto

class MLProcessResponseDTO(BaseModel): 
    job_id: str
    song_id: str
    result_id: str
    asset_id: str
    path: Path
