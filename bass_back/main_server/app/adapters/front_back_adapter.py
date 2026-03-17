from __future__ import annotations

import asyncio
from typing import Any
from dataclasses import dataclass
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.ports.front_back_port import FrontBackRepositoryPort

@dataclass(frozen=True)
class FrontBackPostgresAdapter(FrontBackRepositoryPort):
    # 💡 db_path 대신 Supabase 접속 URL(db_url)을 받습니다.
    db_url: str

    def _get_engine(self) -> Engine:
        # PostgreSQL 연결 엔진 생성
        return create_engine(self.db_url)

    async def search_songs_with_results(self, *, query: str, limit: int = 10) -> list[dict]:
        # 💡 검색어가 비어있을 경우 예외 처리
        search_query = query.strip() if query else ""
        if not search_query:
            return []

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                # 💡 Postgres/Sqlite 공용 SQL 문법
                # s.select_count 등 컬럼명이 Supabase 테이블과 정확히 일치해야 해!
                sql = text("""
                    SELECT 
                        s.song_id, 
                        s.title, 
                        s.artist,
                        r.result_id, 
                        r.status,   
                        a.asset_id,
                        a.original_audio_path, 
                        a.bass_only_path, 
                        a.bass_removed_path, 
                        a.bass_boosted_path,
                        a.original_tab_path, 
                        a.root_tab_path
                    FROM songs s
                    LEFT JOIN results r ON s.song_id = r.song_id
                    LEFT JOIN assets a ON r.result_id = a.result_id
                    WHERE s.title ILIKE :query OR s.artist ILIKE :query
                    ORDER BY s.select_count DESC, s.updated_at DESC
                    LIMIT :limit
                """)
                
                # 💡 ILIKE 사용: PostgreSQL에서 대소문자 구분 없이 검색하기 위함
                # (SQLite는 LIKE가 기본적으로 대소문자 구분을 안 하지만, Postgres는 구분하거든!)
                result = conn.execute(sql, {
                    "query": f"%{search_query}%",
                    "limit": limit
                })
                
                # result.mappings()를 사용하여 딕셔너리 리스트로 변환
                return [dict(row) for row in result.mappings()]

        # 비동기 처리를 위해 스레드에서 실행
        return await asyncio.to_thread(_query)