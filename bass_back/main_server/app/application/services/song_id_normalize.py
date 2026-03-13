# app/application/services/song_id_normalize.py
from __future__ import annotations

import re

def normalize_text(raw: str) -> str:
    """
    곡/아티스트 정규화 규칙
    - 소문자
    - 공백/특수문자 제거
    - 한글/영문/숫자만 허용
    """
    lowered: str = raw.strip().lower()
    normalized: str = re.sub(
        pattern=r"[^0-9a-z가-힣]+",
        repl="",
        string=lowered,
    )
    return normalized
