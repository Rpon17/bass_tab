import sys
from pathlib import Path

# tests/의 상위 폴더(= main_server)를 import path에 추가
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
