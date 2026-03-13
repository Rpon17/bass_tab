from __future__ import annotations

from dataclasses import dataclass, field

from app.application.services.now_time import utc_now_iso


@dataclass
class Asset:
    asset_id: str
    result_id: str

    original_audio_path: str
    bass_only_path: str | None
    bass_removed_path: str | None
    bass_boosted_path: str | None

    original_tab_path: str
    root_tab_path: str

    created_at: str = field(default_factory=utc_now_iso)