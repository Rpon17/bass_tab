from __future__ import annotations

import asyncio
from typing import Any
from dataclasses import dataclass, field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.ports.front_back_port import FrontBackRepositoryPort

@dataclass(frozen=True)
class FrontBackPostgresAdapter(FrontBackRepositoryPort):
    # Supabase 접속 URL(db_url)을 받습니다.
    db_url: str

    def _get_engine(self) -> Engine:
        # PostgreSQL 연결 엔진 생성
        return create_engine(self.db_url)

    async def search_songs_with_results(self, *, query: str, limit: int = 10) -> list[dict]:
        # 검색어가 비어있을 경우 예외 처리
        search_query = query.strip() if query else ""
        if not search_query:
            return []

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                # SQL 문법: ILIKE를 사용하여 대소문자 구분 없이 검색
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
                
                result = conn.execute(sql, {
                    "query": f"%{search_query}%",
                    "limit": limit
                })
                
                # result.mappings()를 사용하여 딕셔너리 리스트로 변환
                rows = [dict(row) for row in result.mappings()]

                # ✅ 데이터 정제 로직 (슬래시 보정 및 경로 오타 수정)
                path_keys = [
                    "original_audio_path", "bass_only_path", "bass_removed_path", 
                    "bass_boosted_path", "original_tab_path", "root_tab_path"
                ]

                for row in rows:
                    for key in path_keys:
                        val = row.get(key)
                        if val and isinstance(val, str):
                            # 1. 모든 역슬래시(\)를 슬래시(/)로 변환
                            fixed_val = val.replace("\\", "/")
                            
                            # 2. https:/ 를 https:// 로 보정 (슬래시가 1개인 경우 대비)
                            if "https:/" in fixed_val and "https://" not in fixed_val:
                                fixed_val = fixed_val.replace("https:/", "https://")
                            
                            # 3. 🚨 [경로 교정] DB의 'assets'를 실제 경로인 'asset'으로 수정
                            # DB 저장값과 실제 스토리지 경로가 다를 때 발생하는 404 에러 방지
                            if "/assets/" in fixed_val:
                                fixed_val = fixed_val.replace("/assets/", "/asset/")
                            
                            row[key] = fixed_val
                
                return rows

        # 비동기 처리를 위해 스레드에서 실행
        return await asyncio.to_thread(_query)