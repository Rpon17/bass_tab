from __future__ import annotations

import asyncio
import traceback
from typing import Any
from dataclasses import dataclass
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.domain.results_domain import Result
from app.application.services.now_time import utc_now_iso


@dataclass(frozen=True)
class ResultRepositoryPostgresAdapter(ResultRepositoryPort):
    # 💡 이제 db_path(파일경로)가 아닌 db_url(Supabase 주소)을 받습니다.
    db_url: str 

    def _get_engine(self) -> Engine:
        # PostgreSQL 연결 최적화를 위해 엔진을 생성합니다.
        return create_engine(self.db_url)

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

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT result_id, song_id, source_url, status, error_message, created_at, updated_at 
                    FROM results 
                    WHERE result_id = :result_id 
                    LIMIT 1
                """)
                row = conn.execute(query, {"result_id": result_id_}).fetchone()
                return self._row_to_result(row=row) if row else None
        
        return await asyncio.to_thread(_query)

    async def save(self, *, result: Result) -> None:
        # 1. 필수 값 검증
        r_id = result.result_id.strip() if result.result_id else ""
        s_id = result.song_id.strip() if result.song_id else ""
        
        if not r_id: raise ValueError("result_id is required")
        if not s_id: raise ValueError("song_id is required")

        # 2. 기본값 및 데이터 정리
        url = result.source_url.strip() if result.source_url else "no_url"
        status = result.status.strip() if result.status else "queued"
        err_msg = result.error_message.strip() if result.error_message else None
        c_at = result.created_at if result.created_at else utc_now_iso()
        u_at = result.updated_at if result.updated_at else utc_now_iso()

        def _execute():
            engine = self._get_engine()
            try:
                with engine.connect() as conn:
                    # 💡 ON CONFLICT 문구는 PostgreSQL에서 동시성 문제를 방지하는 가장 안전한 방법입니다.
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
                    print(f"[SUCCESS] Result saved to Supabase: {r_id}", flush=True)
            except Exception as e:
                print(f"[DB_ERROR] Failed to save result {r_id}: {e}")
                print(traceback.format_exc())
                raise e

        await asyncio.to_thread(_execute)

    async def get_all_by_song_id(self, *, song_id: str) -> list[Result]:
        song_id_ = song_id.strip() if song_id else ""
        if not song_id_:
            return []

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT result_id, song_id, source_url, status, error_message, created_at, updated_at 
                    FROM results 
                    WHERE song_id = :song_id 
                    ORDER BY created_at DESC
                """)
                rows = conn.execute(query, {"song_id": song_id_}).fetchall()
                return [self._row_to_result(row=row) for row in rows]
        
        return await asyncio.to_thread(_query)