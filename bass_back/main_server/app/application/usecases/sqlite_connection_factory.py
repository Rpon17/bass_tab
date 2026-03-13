from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class SqliteConnectionFactory:
    """
    SQLite 연결 생성 팩토리.
    - 팩토리 자체는 가볍게 유지(프로세스당 1개 캐시 가능)
    - 실제 연결은 repo에서 cx.connect() 호출 시 열림
        DB 위치와 옵션을 한 곳에 고정
        index.db가 어디 있는지
        foreign_keys ON 할지
        row_factory를 뭘로 할지
    """
    db_path: Path

    # self.db_path를 사용해서 연결을 만든다
    def connect(self) -> sqlite3.Connection:
        
        conn: sqlite3.Connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
        )
        # dict처럼 row["col"]로 접근 가능하게
        conn.row_factory = sqlite3.Row
        # 외래키 제약 활성화 (SQLite는 기본 OFF라서 매 커넥션마다 켜야 안전)
        conn.execute("PRAGMA foreign_keys = ON;")
        # (선택) 동시성/읽기성능을 위한 WAL 모드
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn
