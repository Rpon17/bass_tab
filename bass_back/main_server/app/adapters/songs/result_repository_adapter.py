from __future__ import annotations

import asyncio
import sqlite3
import traceback
from dataclasses import dataclass

from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.domain.results_domain import Result
from app.application.services.now_time import utc_now_iso


@dataclass(frozen=True)
class ResultRepositorySqliteAdapter(ResultRepositoryPort):
    db_path: str

    def _connect(self) -> sqlite3.Connection:
        conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_result(self, *, row: sqlite3.Row) -> Result:
        return Result(
            result_id=str(row["result_id"]),
            song_id=str(row["song_id"]),
            source_url=str(row["source_url"]),
            status=str(row["status"]),
            error_message=None if row["error_message"] is None else str(row["error_message"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    async def get_by_result_id(self, *, result_id: str) -> Result | None:
        result_id_ = result_id.strip() if result_id else ""
        if not result_id_:
            return None

        def _query() -> Result | None:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM results WHERE result_id = ? LIMIT 1",
                    (result_id_,),
                ).fetchone()
                return self._row_to_result(row=row) if row else None
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def save(self, *, result: Result) -> None:
        """
        검증 로직을 유연하게 수정하여 저장이 끊기지 않도록 함
        """
        # 1. 필수 값 추출 (없으면 빈 문자열)
        r_id = result.result_id.strip() if result.result_id else ""
        s_id = result.song_id.strip() if result.song_id else ""
        
        # 최소한의 필수 식별자만 검증
        if not r_id: raise ValueError("result_id is required")
        if not s_id: raise ValueError("song_id is required")

        # 2. 나머지 값 처리 (기본값 부여)
        url = result.source_url.strip() if result.source_url else "no_url"
        status = result.status.strip() if result.status else "queued"
        err_msg = result.error_message.strip() if result.error_message else None
        c_at = result.created_at if result.created_at else utc_now_iso()
        u_at = result.updated_at if result.updated_at else utc_now_iso()

        def _execute() -> None:
            conn = self._connect()
            try:
                # 외래키 제약 활성화
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute(
                    """
                    INSERT INTO results (
                        result_id, song_id, source_url, status, error_message, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(result_id) DO UPDATE SET
                        status=excluded.status,
                        error_message=excluded.error_message,
                        updated_at=excluded.updated_at
                    """,
                    (r_id, s_id, url, status, err_msg, c_at, u_at),
                )
                conn.commit()
                print(f"[SUCCESS] Result saved: {r_id}", flush=True)
            except sqlite3.Error as e:
                print(f"[DB_ERROR] Failed to save result {r_id}: {e}")
                print(traceback.format_exc()) # 상세 에러 스택 출력
                raise e
            finally:
                conn.close()

        await asyncio.to_thread(_execute)
        
        
    # 가져오기 메소드
    async def get_all_by_song_id(self, *, song_id: str) -> list[Result]:
        song_id_ = song_id.strip() if song_id else ""
        if not song_id_:
            return []

        def _query() -> list[Result]:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM results WHERE song_id = ? ORDER BY created_at DESC",
                    (song_id_,),
                ).fetchall()
                # 기존에 쓰던 _row_to_result 메서드를 그대로 재활용합니다.
                return [self._row_to_result(row=row) for row in rows]
            finally:
                conn.close()

        return await asyncio.to_thread(_query)