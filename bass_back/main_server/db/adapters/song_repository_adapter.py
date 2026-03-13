# main_server/app/adapters/db/song_repository_sqlite.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from db.application.ports.song_id_port import SongRepositoryPort
from db.domain.song_domain import Song


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
                """,
                (song_id,),
            ).fetchone()

            if row is None:
                return None

            return self._row_to_song(row=row)
        finally:
            conn.close()

    async def get_by_norm(
        self,
        *,
        norm_title: str,
        norm_artist: str,
    ) -> Song | None:
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
                (norm_title, norm_artist),
            ).fetchone()

            if row is None:
                return None

            return self._row_to_song(row=row)
        finally:
            conn.close()

    async def search_by_norm_title_prefix(
        self,
        *,
        norm_title_prefix: str,
        limit: int = 10,
    ) -> list[Song]:
        conn: sqlite3.Connection = self._connect()
        try:
            rows: list[sqlite3.Row] = conn.execute(
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
                (f"{norm_title_prefix}%", limit),
            ).fetchall()

            return [self._row_to_song(row=row) for row in rows]
        finally:
            conn.close()

    async def save(self, *, song: Song) -> None:
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
                    song.song_id,
                    song.title,
                    song.artist,
                    song.norm_title,
                    song.norm_artist,
                    song.created_at,
                    song.updated_at,
                    song.select_count,
                ),
            )
            conn.commit()
        finally:
            conn.close()