from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass

from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.domain.results_domain import Result


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
        result_id_: str = result_id.strip()
        if len(result_id_) == 0:
            return None

        def _query() -> Result | None:
            conn: sqlite3.Connection = self._connect()
            try:
                row: sqlite3.Row | None = conn.execute(
                    """
                    SELECT
                        result_id,
                        song_id,
                        source_url,
                        status,
                        error_message,
                        created_at,
                        updated_at
                    FROM results
                    WHERE result_id = ?
                    LIMIT 1
                    """,
                    (result_id_,),
                ).fetchone()

                if row is None:
                    return None

                return self._row_to_result(row=row)
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def list_by_song_id(
        self,
        *,
        song_id: str,
    ) -> list[Result]:
        song_id_: str = song_id.strip()
        if len(song_id_) == 0:
            return []

        def _query() -> list[Result]:
            conn: sqlite3.Connection = self._connect()
            try:
                rows: list[sqlite3.Row] = conn.execute(
                    """
                    SELECT
                        result_id,
                        song_id,
                        source_url,
                        status,
                        error_message,
                        created_at,
                        updated_at
                    FROM results
                    WHERE song_id = ?
                    ORDER BY created_at DESC
                    """,
                    (song_id_,),
                ).fetchall()

                return [self._row_to_result(row=row) for row in rows]
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def save(self, *, result: Result) -> None:
        result_id_: str = result.result_id.strip()
        song_id_: str = result.song_id.strip()
        source_url_: str = result.source_url.strip()
        status_: str = result.status.strip()
        created_at_: str = result.created_at.strip()
        updated_at_: str = result.updated_at.strip()
        error_message_: str | None = None if result.error_message is None else result.error_message.strip()

        if len(result_id_) == 0:
            raise ValueError("result.result_id must not be empty")
        if len(song_id_) == 0:
            raise ValueError("result.song_id must not be empty")
        if len(source_url_) == 0:
            raise ValueError("result.source_url must not be empty")
        if len(status_) == 0:
            raise ValueError("result.status must not be empty")
        if len(created_at_) == 0:
            raise ValueError("result.created_at must not be empty")
        if len(updated_at_) == 0:
            raise ValueError("result.updated_at must not be empty")

        def _execute() -> None:
            conn: sqlite3.Connection = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO results (
                        result_id,
                        song_id,
                        source_url,
                        status,
                        error_message,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_id_,
                        song_id_,
                        source_url_,
                        status_,
                        error_message_,
                        created_at_,
                        updated_at_,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_execute)