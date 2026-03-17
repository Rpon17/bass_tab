from __future__ import annotations

import traceback
from typing import Any
from dataclasses import dataclass
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.domain.results_domain import Result
from app.application.services.now_time import utc_now_iso


@dataclass(frozen=True)
class ResultRepositorySqliteAdapter(ResultRepositoryPort):
    db_path: str
    def _get_engine(self) -> Engine:
        return create_engine(self.db_path)

    def _row_to_result(self, *, row: Any) -> Result:
        return Result(
            result_id=str(row.result_id),
            song_id=str(row.song_id),
            source_url=str(row.source_url),
            status=str(row.status),
            error_message=None if row.error_message is None else str(row.error_message),
            created_at=str(row.created_at),
            updated_at=str(row.updated_at),
        )

    async def get_by_result_id(self, *, result_id: str) -> Result | None:
        result_id_ = result_id.strip() if result_id else ""
        if not result_id_:
            return None

        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT * FROM results 
                WHERE result_id = :result_id 
                LIMIT 1
            """)
            row = conn.execute(query, {"result_id": result_id_}).fetchone()
            return self._row_to_result(row=row) if row else None

    async def save(self, *, result: Result) -> None:
        # 1. 필수 값 추출 및 기본값 처리
        r_id = result.result_id.strip() if result.result_id else ""
        s_id = result.song_id.strip() if result.song_id else ""
        
        if not r_id: raise ValueError("result_id is required")
        if not s_id: raise ValueError("song_id is required")

        url = result.source_url.strip() if result.source_url else "no_url"
        status = result.status.strip() if result.status else "queued"
        err_msg = result.error_message.strip() if result.error_message else None
        c_at = result.created_at if result.created_at else utc_now_iso()
        u_at = result.updated_at if result.updated_at else utc_now_iso()

        engine = self._get_engine()
        try:
            with engine.connect() as conn:
                # 💡 SQLAlchemy text()를 이용한 UPSERT (Insert or Update) 문법
                # PostgreSQL과 SQLite(최신버전) 공용 문법입니다.
                query = text("""
                    INSERT INTO results (
                        result_id, song_id, source_url, status, error_message, created_at, updated_at
                    )
                    VALUES (
                        :result_id, :song_id, :source_url, :status, :error_message, :created_at, :updated_at
                    )
                    ON CONFLICT(result_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        error_message = EXCLUDED.error_message,
                        updated_at = EXCLUDED.updated_at
                """)
                
                conn.execute(query, {
                    "result_id": r_id,
                    "song_id": s_id,
                    "source_url": url,
                    "status": status,
                    "error_message": err_msg,
                    "created_at": c_at,
                    "updated_at": u_at
                })
                conn.commit()
                print(f"[SUCCESS] Result saved: {r_id}", flush=True)
        except Exception as e:
            print(f"[DB_ERROR] Failed to save result {r_id}: {e}")
            print(traceback.format_exc())
            raise e

    async def get_all_by_song_id(self, *, song_id: str) -> list[Result]:
        song_id_ = song_id.strip() if song_id else ""
        if not song_id_:
            return []

        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT * FROM results 
                WHERE song_id = :song_id 
                ORDER BY created_at DESC
            """)
            rows = conn.execute(query, {"song_id": song_id_}).fetchall()
            return [self._row_to_result(row=row) for row in rows]