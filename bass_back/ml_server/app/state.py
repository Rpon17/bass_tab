# ml_server/app/state.py
from __future__ import annotations
from typing import Dict, Any

# job_id -> 상태
ML_JOBS: Dict[str, Dict[str, Any]] = {}
