# main_server/app/adapters/db/song_repository_sqlite.py
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass

from app.application.ports.song_repository_port import SongRepositoryPort
from app.domain.songs_domain import Song


@dataclass(frozen=True)
class SongRepositorySqliteAdapter(SongRepositoryPort):
    db_path: str

    def _connect(self) -> sqlite3.Connection:
        conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_song(self, *, row: sqlite3.Row) -> Song:
        return Song(
            song_id=str(row["song_id"]),
            title=str(row["title"]),
            artist=str(row["artist"]),
            norm_title=str(row["norm_title"]),
            norm_artist=str(row["norm_artist"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            select_count=int(row["select_count"]),
        )

    async def get_by_song_id(self, *, song_id: str) -> Song | None:
        song_id_ = song_id.strip()
        if len(song_id_) == 0:
            return None

        def _query() -> Song | None:
            conn: sqlite3.Connection = self._connect()
            try:
                row: sqlite3.Row | None = conn.execute(
                    """
                    SELECT
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    FROM songs
                    WHERE song_id = ?
                    LIMIT 1
                    """,
                    (song_id_,),
                ).fetchone()

                if row is None:
                    return None

                return self._row_to_song(row=row)
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def get_by_norm(
        self,
        *,
        norm_title: str,
        norm_artist: str,
    ) -> Song | None:
        norm_title_ = norm_title.strip()
        norm_artist_ = norm_artist.strip()

        if len(norm_title_) == 0 or len(norm_artist_) == 0:
            return None

        def _query() -> Song | None:
            conn: sqlite3.Connection = self._connect()
            try:
                row: sqlite3.Row | None = conn.execute(
                    """
                    SELECT
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    FROM songs
                    WHERE norm_title = ?
                      AND norm_artist = ?
                    LIMIT 1
                    """,
                    (norm_title_, norm_artist_),
                ).fetchone()

                if row is None:
                    return None

                return self._row_to_song(row=row)
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def search_by_norm_title_prefix(
        self,
        *,
        norm_title_prefix: str,
        limit: int = 10,
    ) -> list[Song]:
        prefix: str = norm_title_prefix.strip()
        limit_: int = int(limit)

        if len(prefix) == 0:
            return []

        if limit_ <= 0:
            return []

        like_pattern: str = f"{prefix}%"

        def _query() -> list[Song]:
            conn: sqlite3.Connection = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    FROM songs
                    WHERE norm_title LIKE ?
                    ORDER BY select_count DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (like_pattern, limit_),
                ).fetchall()

                return [self._row_to_song(row=row) for row in rows]
            finally:
                conn.close()

        return await asyncio.to_thread(_query)
    
    async def save(self, *, song: Song) -> None:
        song_id_: str = song.song_id.strip()
        title_: str = song.title.strip()
        artist_: str = song.artist.strip()
        norm_title_: str = song.norm_title.strip()
        norm_artist_: str = song.norm_artist.strip()
        created_at_: str = song.created_at.strip()
        updated_at_: str = song.updated_at.strip()

        if len(song_id_) == 0:
            raise ValueError("song.song_id must not be empty")
        if len(title_) == 0:
            raise ValueError("song.title must not be empty")
        if len(artist_) == 0:
            raise ValueError("song.artist must not be empty")
        if len(norm_title_) == 0:
            raise ValueError("song.norm_title must not be empty")
        if len(norm_artist_) == 0:
            raise ValueError("song.norm_artist must not be empty")
        if len(created_at_) == 0:
            raise ValueError("song.created_at must not be empty")
        if len(updated_at_) == 0:
            raise ValueError("song.updated_at must not be empty")

        def _execute() -> None:
            conn: sqlite3.Connection = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO songs (
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        song_id_,
                        title_,
                        artist_,
                        norm_title_,
                        norm_artist_,
                        created_at_,
                        updated_at_,
                        int(song.select_count),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_execute)