from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

"""  
    찾을때마다 설정을 부여함
"""
@dataclass(frozen=True)
class SqliteConnectionFactory:
    db_path: Path
    # SQLite DB에 연결할 때마다 row 접근,외래키 설정이 적용된 안전한 연결을 위함
    # conn은 sql연결 객체임
    def connect(self) -> sqlite3.Connection:
        conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
