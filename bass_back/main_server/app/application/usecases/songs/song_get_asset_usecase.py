from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.domain.songs_domain import Result
from bass_back.main_server.app.application.ports.song_result_repository_port import SongAssetRepository


@dataclass(frozen=True)
class GetAssetUseCase:
    asset_repo: SongAssetRepository

    async def execute(self, *, result_id: str) -> Result:
        asset: Optional[Result] = await self.asset_repo.get_by_id(result_id=result_id)
        if asset is None:
            raise KeyError("asset not found")
        return asset
