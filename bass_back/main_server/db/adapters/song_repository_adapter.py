from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import create_engine, text , Row
from sqlalchemy.engine import Engine

from db.application.ports.song_id_port import SongRepositoryPort
from db.domain.song_domain import Song

@dataclass(frozen=True)
class SongRepositorySqliteAdapter(SongRepositoryPort):
    db_path: str 

    def _get_engine(self) -> Engine:
        return create_engine(self.db_path)

    def _row_to_song(self, *, row: Row) -> Song:
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
        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                FROM songs
                WHERE song_id = :song_id
            """)
            result = conn.execute(query, {"song_id": song_id}).fetchone()

            if result is None:
                return None
            return self._row_to_song(row=result)

    async def get_by_norm(self, *, norm_title: str, norm_artist: str) -> Song | None:
        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                FROM songs
                WHERE norm_title = :norm_title AND norm_artist = :norm_artist
                LIMIT 1
            """)
            result = conn.execute(query, {"norm_title": norm_title, "norm_artist": norm_artist}).fetchone()

            if result is None:
                return None
            return self._row_to_song(row=result)

    async def search_by_norm_title_prefix(self, *, norm_title_prefix: str, limit: int = 10) -> list[Song]:
        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                FROM songs
                WHERE norm_title LIKE :prefix
                ORDER BY select_count DESC, updated_at DESC
                LIMIT :limit
            """)
            rows = conn.execute(query, {"prefix": f"{norm_title_prefix}%", "limit": limit}).fetchall()
            return [self._row_to_song(row=row) for row in rows]

    async def save(self, *, song: Song) -> None:
        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                INSERT INTO songs (
                    song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                )
                VALUES (
                    :song_id, :title, :artist, :norm_title, :norm_artist, :created_at, :updated_at, :select_count
                )
            """)
            conn.execute(query, {
                "song_id": song.song_id,
                "title": song.title,
                "artist": song.artist,
                "norm_title": song.norm_title,
                "norm_artist": song.norm_artist,
                "created_at": song.created_at,
                "updated_at": song.updated_at,
                "select_count": song.select_count,
            })
            conn.commit()  # 변경사항 반영
            print("song 테이블 저장 완료")