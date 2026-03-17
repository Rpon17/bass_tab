# main_server/app/application/usecases/songs/asset_create_usecase.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.application.ports.asset_repository_port import AssetRepositoryPort
from app.domain.asset_domain import Asset
from app.application.services.path_maker import audio_path, tab_path


@dataclass(frozen=True)
class CreateAssetUseCase:
    asset_repository: AssetRepositoryPort

    async def execute(
        self,
        *,
        result_id: str,
        asset_id: str,
        path: str,
    ) -> Asset:
        existing: Asset | None = await self.asset_repository.get_by_result_id(
            result_id=result_id,
        )
        if existing is not None:
            return existing

        base_path: Path = Path(path)

        asset: Asset = Asset(
            asset_id=asset_id,
            result_id=result_id,
            original_audio_path=audio_path(base_path,asset_id, "original.wav"),
            bass_only_path=audio_path(base_path,asset_id, "bass_only.wav"),
            bass_removed_path=audio_path(base_path,asset_id, "bass_removed.wav"),
            bass_boosted_path=audio_path(base_path,asset_id, "bass_boosted.wav"),
            original_tab_path=tab_path(base_path,asset_id, "original_tab.json"),
            root_tab_path=tab_path(base_path,asset_id, "root_tab.json"),
        )

        await self.asset_repository.save(asset=asset)
        return asset