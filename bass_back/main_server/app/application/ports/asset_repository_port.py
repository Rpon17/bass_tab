from __future__ import annotations

from typing import Protocol

from app.domain.asset_domain import Asset


class AssetRepositoryPort(Protocol):
    async def get_by_asset_id(self, *, asset_id: str) -> Asset | None:
        ...

    async def get_by_result_id(self, *, result_id: str) -> Asset | None:
        ...

    async def save(self, *, asset: Asset) -> None:
        ...