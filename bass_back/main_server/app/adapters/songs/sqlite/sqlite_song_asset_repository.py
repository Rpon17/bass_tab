from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from app.domain.songs_domain import Asset
from app.adapters.songs.sqlite_connection import SqliteConnectionFactory
from bass_back.main_server.app.application.ports.song_result_repository_port import SongAssetRepository


@dataclass(frozen=True)
class SqliteSongAssetRepository(SongAssetRepository):
    cx: SqliteConnectionFactory

    def _row_to_asset(self, r: Any) -> Asset:
        return Asset(
            asset_id=str(r["asset_id"]),
            storage_path=str(r["storage_path"]),
            content_type=str(r["content_type"]),
        )

    async def get_by_id(self, *, asset_id: str) -> Optional[Asset]:
        asset_id_: str = asset_id.strip()
        if len(asset_id_) == 0:
            return None

        def _get() -> Optional[Asset]:
            with self.cx.connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                      asset_id,
                      storage_path,
                      content_type
                    FROM assets
                    WHERE asset_id = ?
                    """,
                    (asset_id_,),
                ).fetchone()
            return None if row is None else self._row_to_asset(row)

        return await asyncio.to_thread(_get)
