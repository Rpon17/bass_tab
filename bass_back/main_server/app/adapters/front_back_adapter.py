from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.ports.front_back_port import FrontBackRepositoryPort

@dataclass(frozen=True)
class FrontBackSqliteAdapter(FrontBackRepositoryPort):
    db_path: str

    # 1. 공통 엔진 생성
    def _get_engine(self) -> Engine:
        return create_engine(self.db_path)

    async def search_songs_with_results(self, *, query: str, limit: int = 10) -> list[dict]:
        engine = self._get_engine()
        with engine.connect() as conn:
            # 💡 SQLAlchemy의 text()와 :변수명 방식을 사용하여 Postgres/Sqlite 호환
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
                WHERE s.title LIKE :query OR s.artist LIKE :query
                ORDER BY s.select_count DESC, s.updated_at DESC
                LIMIT :limit
            """)
            
            # 파라미터 전달
            result = conn.execute(sql, {
                "query": f"%{query}%",
                "limit": limit
            })
            
            # 💡 SQLAlchemy의 Row 객체를 dict로 변환
            # result.mappings()를 사용하면 컬럼명을 키로 가진 딕셔너리처럼 쓸 수 있습니다.
            return [dict(row) for row in result.mappings()]