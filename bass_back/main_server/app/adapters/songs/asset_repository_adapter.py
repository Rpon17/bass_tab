from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.ports.asset_repository_port import AssetRepositoryPort
from app.domain.asset_domain import Asset


@dataclass(frozen=True)
class AssetRepositorySqliteAdapter(AssetRepositoryPort):
    db_path: str

    # 1. 공통 엔진 생성
    def _get_engine(self) -> Engine:
        return create_engine(self.db_path)

    def _row_to_asset(self, *, row: Any) -> Asset:
        # SQLAlchemy의 속성 접근(.) 방식을 사용합니다.
        return Asset(
            asset_id=str(row.asset_id),
            result_id=str(row.result_id),
            original_audio_path=str(row.original_audio_path),
            bass_only_path=None if row.bass_only_path is None else str(row.bass_only_path),
            bass_removed_path=None if row.bass_removed_path is None else str(row.bass_removed_path),
            bass_boosted_path=None if row.bass_boosted_path is None else str(row.bass_boosted_path),
            original_tab_path=str(row.original_tab_path),
            root_tab_path=str(row.root_tab_path),
            created_at=str(row.created_at),
        )

    async def get_by_asset_id(self, *, asset_id: str) -> Asset | None:
        asset_id_: str = asset_id.strip()
        if len(asset_id_) == 0:
            return None

        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    asset_id, result_id, original_audio_path, 
                    bass_only_path, bass_removed_path, bass_boosted_path, 
                    original_tab_path, root_tab_path, created_at
                FROM assets
                WHERE asset_id = :asset_id
                LIMIT 1
            """)
            row = conn.execute(query, {"asset_id": asset_id_}).fetchone()

            if row is None:
                return None

            return self._row_to_asset(row=row)

    async def get_by_result_id(self, *, result_id: str) -> Asset | None:
        result_id_: str = result_id.strip()
        if len(result_id_) == 0:
            return None

        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    asset_id, result_id, original_audio_path, 
                    bass_only_path, bass_removed_path, bass_boosted_path, 
                    original_tab_path, root_tab_path, created_at
                FROM assets
                WHERE result_id = :result_id
                LIMIT 1
            """)
            row = conn.execute(query, {"result_id": result_id_}).fetchone()

            if row is None:
                return None

            return self._row_to_asset(row=row)

    async def save(self, *, asset: Asset) -> None:
        # 1. 값 검증 및 정리
        asset_id_ = asset.asset_id.strip()
        result_id_ = asset.result_id.strip()
        orig_audio_ = asset.original_audio_path.strip()
        orig_tab_ = asset.original_tab_path.strip()
        root_tab_ = asset.root_tab_path.strip()
        created_at_ = asset.created_at.strip()

        # 필수값 체크
        if not asset_id_: raise ValueError("asset.asset_id must not be empty")
        if not result_id_: raise ValueError("asset.result_id must not be empty")
        if not orig_audio_: raise ValueError("asset.original_audio_path must not be empty")

        # 2. 선택적 경로 처리
        b_only = asset.bass_only_path.strip() if asset.bass_only_path and asset.bass_only_path.strip() else None
        b_rem = asset.bass_removed_path.strip() if asset.bass_removed_path and asset.bass_removed_path.strip() else None
        b_boost = asset.bass_boosted_path.strip() if asset.bass_boosted_path and asset.bass_boosted_path.strip() else None

        engine = self._get_engine()
        with engine.connect() as conn:
            query = text("""
                INSERT INTO assets (
                    asset_id, result_id, original_audio_path, 
                    bass_only_path, bass_removed_path, bass_boosted_path, 
                    original_tab_path, root_tab_path, created_at
                )
                VALUES (
                    :asset_id, :result_id, :orig_audio, 
                    :b_only, :b_rem, :b_boost, 
                    :orig_tab, :root_tab, :created_at
                )
            """)
            conn.execute(query, {
                "asset_id": asset_id_,
                "result_id": result_id_,
                "orig_audio": orig_audio_,
                "b_only": b_only,
                "b_rem": b_rem,
                "b_boost": b_boost,
                "orig_tab": orig_tab_,
                "root_tab": root_tab_,
                "created_at": created_at_
            })
            conn.commit()
            print(f"[SUCCESS] Asset saved: {asset_id_}")