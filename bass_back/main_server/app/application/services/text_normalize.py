from __future__ import annotations
import re

""" 
    정규화 코드
    여기서는 다 소문자로 하고 0~9 a~z 한글만되게
"""
def normalize_text(raw: str) -> str:
    lowered: str = raw.lower()
    cleaned: str = re.sub(pattern=r"[^0-9a-z가-힣]+", repl="", string=lowered)
    return cleaned