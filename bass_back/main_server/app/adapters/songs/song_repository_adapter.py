from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.ports.song_repository_port import SongRepositoryPort
from app.domain.songs_domain import Song

@dataclass(frozen=True)
class SongRepositoryPostgresAdapter(SongRepositoryPort):
    db_url: str  # 💡 이제 db_path(파일경로)가 아니라 db_url(Supabase 주소)을 받아!

    def _get_engine(self) -> Engine:
        # SQLAlchemy 엔진을 통해 PostgreSQL(Supabase)에 연결해
        return create_engine(self.db_url)

    def _row_to_song(self, *, row: Any) -> Song:
        # SQLAlchemy Row 객체를 Song 도메인 모델로 변환해
        return Song(
            song_id=str(row.song_id),
            title=str(row.title),
            artist=str(row.artist),
            norm_title=str(row.norm_title),
            norm_artist=str(row.norm_artist),
            created_at=str(row.created_at),
            updated_at=str(row.updated_at),
            select_count=int(row.select_count),
        )

    async def get_by_song_id(self, *, song_id: str) -> Song | None:
        song_id_ = song_id.strip()
        if not song_id_: return None

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                    FROM songs WHERE song_id = :song_id LIMIT 1
                """)
                row = conn.execute(query, {"song_id": song_id_}).fetchone()
                return self._row_to_song(row=row) if row else None
        
        return await asyncio.to_thread(_query)

    async def get_by_norm(self, *, norm_title: str, norm_artist: str) -> Song | None:
        nt, na = norm_title.strip(), norm_artist.strip()
        if not nt or not na: return None

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                    FROM songs WHERE norm_title = :nt AND norm_artist = :na LIMIT 1
                """)
                row = conn.execute(query, {"nt": nt, "na": na}).fetchone()
                return self._row_to_song(row=row) if row else None

        return await asyncio.to_thread(_query)

    async def search_by_norm_title_prefix(self, *, norm_title_prefix: str, limit: int = 10) -> list[Song]:
        prefix = norm_title_prefix.strip()
        if not prefix or limit <= 0: return []

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                    FROM songs 
                    WHERE norm_title LIKE :prefix 
                    ORDER BY select_count DESC, updated_at DESC LIMIT :limit
                """)
                rows = conn.execute(query, {"prefix": f"{prefix}%", "limit": limit}).fetchall()
                return [self._row_to_song(row=row) for row in rows]

        return await asyncio.to_thread(_query)
    
    async def save(self, *, song: Song) -> None:
        def _execute():
            engine = self._get_engine()
            with engine.connect() as conn:
                # 💡 PostgreSQL 전용 UPSERT 문법 (중복 시 업데이트)
                query = text("""
                    INSERT INTO songs (
                        song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                    ) VALUES (
                        :id, :t, :a, :nt, :na, :ca, :ua, :sc
                    )
                    ON CONFLICT (song_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        artist = EXCLUDED.artist,
                        updated_at = EXCLUDED.updated_at,
                        select_count = songs.select_count + 1
                """)
                conn.execute(query, {
                    "id": song.song_id, "t": song.title, "a": song.artist,
                    "nt": song.norm_title, "na": song.norm_artist,
                    "ca": song.created_at, "ua": song.updated_at, "sc": song.select_count
                })
                conn.commit()

        await asyncio.to_thread(_execute)