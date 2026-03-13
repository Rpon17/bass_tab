from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass

from app.application.ports.asset_repository_port import AssetRepositoryPort
from app.domain.asset_domain import Asset


@dataclass(frozen=True)
class AssetRepositorySqliteAdapter(AssetRepositoryPort):
    db_path: str

    def _connect(self) -> sqlite3.Connection:
        conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_asset(self, *, row: sqlite3.Row) -> Asset:
        return Asset(
            asset_id=str(row["asset_id"]),
            result_id=str(row["result_id"]),
            original_audio_path=str(row["original_audio_path"]),
            bass_only_path=None if row["bass_only_path"] is None else str(row["bass_only_path"]),
            bass_removed_path=None if row["bass_removed_path"] is None else str(row["bass_removed_path"]),
            bass_boosted_path=None if row["bass_boosted_path"] is None else str(row["bass_boosted_path"]),
            original_tab_path=str(row["original_tab_path"]),
            root_tab_path=str(row["root_tab_path"]),
            created_at=str(row["created_at"]),
        )

    async def get_by_asset_id(self, *, asset_id: str) -> Asset | None:
        asset_id_: str = asset_id.strip()
        if len(asset_id_) == 0:
            return None

        def _query() -> Asset | None:
            conn: sqlite3.Connection = self._connect()
            try:
                row: sqlite3.Row | None = conn.execute(
                    """
                    SELECT
                        asset_id,
                        result_id,
                        original_audio_path,
                        bass_only_path,
                        bass_removed_path,
                        bass_boosted_path,
                        original_tab_path,
                        root_tab_path,
                        created_at
                    FROM assets
                    WHERE asset_id = ?
                    LIMIT 1
                    """,
                    (asset_id_,),
                ).fetchone()

                if row is None:
                    return None

                return self._row_to_asset(row=row)
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def get_by_result_id(self, *, result_id: str) -> Asset | None:
        result_id_: str = result_id.strip()
        if len(result_id_) == 0:
            return None

        def _query() -> Asset | None:
            conn: sqlite3.Connection = self._connect()
            try:
                row: sqlite3.Row | None = conn.execute(
                    """
                    SELECT
                        asset_id,
                        result_id,
                        original_audio_path,
                        bass_only_path,
                        bass_removed_path,
                        bass_boosted_path,
                        original_tab_path,
                        root_tab_path,
                        created_at
                    FROM assets
                    WHERE result_id = ?
                    LIMIT 1
                    """,
                    (result_id_,),
                ).fetchone()

                if row is None:
                    return None

                return self._row_to_asset(row=row)
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def save(self, *, asset: Asset) -> None:
        asset_id_: str = asset.asset_id.strip()
        result_id_: str = asset.result_id.strip()

        original_audio_path_: str = asset.original_audio_path.strip()
        bass_only_path_: str | None = None if asset.bass_only_path is None else asset.bass_only_path.strip()
        bass_removed_path_: str | None = None if asset.bass_removed_path is None else asset.bass_removed_path.strip()
        bass_boosted_path_: str | None = None if asset.bass_boosted_path is None else asset.bass_boosted_path.strip()

        original_tab_path_: str = asset.original_tab_path.strip()
        root_tab_path_: str = asset.root_tab_path.strip()

        created_at_: str = asset.created_at.strip()

        if len(asset_id_) == 0:
            raise ValueError("asset.asset_id must not be empty")
        if len(result_id_) == 0:
            raise ValueError("asset.result_id must not be empty")
        if len(original_audio_path_) == 0:
            raise ValueError("asset.original_audio_path must not be empty")
        if len(original_tab_path_) == 0:
            raise ValueError("asset.original_tab_path must not be empty")
        if len(root_tab_path_) == 0:
            raise ValueError("asset.root_tab_path must not be empty")
        if len(created_at_) == 0:
            raise ValueError("asset.created_at must not be empty")

        if bass_only_path_ is not None and len(bass_only_path_) == 0:
            bass_only_path_ = None
        if bass_removed_path_ is not None and len(bass_removed_path_) == 0:
            bass_removed_path_ = None
        if bass_boosted_path_ is not None and len(bass_boosted_path_) == 0:
            bass_boosted_path_ = None

        def _execute() -> None:
            conn: sqlite3.Connection = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO assets (
                        asset_id,
                        result_id,
                        original_audio_path,
                        bass_only_path,
                        bass_removed_path,
                        bass_boosted_path,
                        original_tab_path,
                        root_tab_path,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset_id_,
                        result_id_,
                        original_audio_path_,
                        bass_only_path_,
                        bass_removed_path_,
                        bass_boosted_path_,
                        original_tab_path_,
                        root_tab_path_,
                        created_at_,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_execute)