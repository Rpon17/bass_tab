from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.application.ports.asset_repository_port import AssetRepositoryPort
from app.domain.results_domain import Result
from app.application.services.path_maker import audio_path, tab_path


@dataclass(frozen=True)
class CreateResultUseCase:
    asset_repository: AssetRepositoryPort

    async def execute(
        self,
        *,
        result_id: str,
        asset_id: str,
        path: str,
    ) -> Result:
        base_path: Path = Path(path)

        asset: Result = Result.create(
            asset_id_=asset_id,
            result_id_=result_id,
            original_audio_path_=audio_path(base_path, "original.wav"),
            bass_only_path_=audio_path(base_path, "bass_only.wav"),
            bass_removed_path_=audio_path(base_path, "bass_removed.wav"),
            bass_boosted_path_=audio_path(base_path, "bass_boosted.wav"),
            original_tab_path_=tab_path(base_path, "original_tab.json"),
            root_tab_path_=tab_path(base_path, "root_tab.json"),
        )

        await self.asset_repository.save(asset=asset)
        return asset