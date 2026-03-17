from __future__ import annotations

import asyncio
from typing import Any
from dataclasses import dataclass
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.ports.asset_repository_port import AssetRepositoryPort
from app.domain.asset_domain import Asset


@dataclass(frozen=True)
class AssetRepositoryPostgresAdapter(AssetRepositoryPort):
    # 💡 db_path 대신 Supabase 접속 URL을 받도록 변경
    db_url: str 

    def _get_engine(self) -> Engine:
        # PostgreSQL 연결 엔진 생성
        return create_engine(self.db_url)

    def _row_to_asset(self, *, row: Any) -> Asset:
        # SQLAlchemy Row 객체에서 안전하게 데이터를 추출하여 Asset 도메인으로 변환
        return Asset(
            asset_id=str(row.asset_id),
            result_id=str(row.result_id),
            original_audio_path=str(row.original_audio_path),
            bass_only_path=str(row.bass_only_path) if row.bass_only_path else None,
            bass_removed_path=str(row.bass_removed_path) if row.bass_removed_path else None,
            bass_boosted_path=str(row.bass_boosted_path) if row.bass_boosted_path else None,
            original_tab_path=str(row.original_tab_path),
            root_tab_path=str(row.root_tab_path),
            created_at=str(row.created_at),
        )

    async def get_by_asset_id(self, *, asset_id: str) -> Asset | None:
        aid = asset_id.strip() if asset_id else ""
        if not aid: return None

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT asset_id, result_id, original_audio_path, 
                           bass_only_path, bass_removed_path, bass_boosted_path, 
                           original_tab_path, root_tab_path, created_at
                    FROM assets WHERE asset_id = :asset_id LIMIT 1
                """)
                row = conn.execute(query, {"asset_id": aid}).fetchone()
                return self._row_to_asset(row=row) if row else None

        return await asyncio.to_thread(_query)

    async def get_by_result_id(self, *, result_id: str) -> Asset | None:
        rid = result_id.strip() if result_id else ""
        if not rid: return None

        def _query():
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT asset_id, result_id, original_audio_path, 
                           bass_only_path, bass_removed_path, bass_boosted_path, 
                           original_tab_path, root_tab_path, created_at
                    FROM assets WHERE result_id = :result_id LIMIT 1
                """)
                row = conn.execute(query, {"result_id": rid}).fetchone()
                return self._row_to_asset(row=row) if row else None

        return await asyncio.to_thread(_query)

    async def save(self, *, asset: Asset) -> None:
        # 1. 값 검증
        aid = asset.asset_id.strip()
        rid = asset.result_id.strip()
        if not aid or not rid:
            raise ValueError("asset_id and result_id are required")

        def _execute():
            engine = self._get_engine()
            with engine.connect() as conn:
                # 💡 Postgres 전용 UPSERT: 이미 있으면 업데이트, 없으면 삽입
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
                    ON CONFLICT (asset_id) DO UPDATE SET
                        bass_only_path = EXCLUDED.bass_only_path,
                        bass_removed_path = EXCLUDED.bass_removed_path,
                        bass_boosted_path = EXCLUDED.bass_boosted_path,
                        original_tab_path = EXCLUDED.original_tab_path,
                        root_tab_path = EXCLUDED.root_tab_path
                """)
                conn.execute(query, {
                    "asset_id": aid,
                    "result_id": rid,
                    "orig_audio": asset.original_audio_path.strip(),
                    "b_only": asset.bass_only_path.strip() if asset.bass_only_path else None,
                    "b_rem": asset.bass_removed_path.strip() if asset.bass_removed_path else None,
                    "b_boost": asset.bass_boosted_path.strip() if asset.bass_boosted_path else None,
                    "orig_tab": asset.original_tab_path.strip(),
                    "root_tab": asset.root_tab_path.strip(),
                    "created_at": asset.created_at.strip()
                })
                conn.commit()
                print(f"[SUCCESS] Asset saved to Supabase: {aid}")

        await asyncio.to_thread(_execute)