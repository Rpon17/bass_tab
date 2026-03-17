from __future__ import annotations

import sqlite3
from pathlib import Path


# 프로젝트 루트 기준 경로
BASE_DIR: Path = Path(__file__).resolve().parents[1]

SCHEMA_PATH: Path = BASE_DIR / "db" / "schema" / "001_init.sql"
DB_PATH: Path = BASE_DIR / "db" / "data" / "index.db"


def init_db() -> None:
    # db/data 디렉토리 보장
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 스키마 SQL 읽기
    schema_sql: str = SCHEMA_PATH.read_text(encoding="utf-8")

    # SQLite 연결 (파일 없으면 자동 생성)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)

    print(f"✅ DB initialized: {DB_PATH}")


if __name__ == "__main__":
    init_db()
