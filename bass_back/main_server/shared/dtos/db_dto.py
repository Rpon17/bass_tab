from __future__ import annotations

from dataclasses import dataclass

"""  
    db에서 저장되는 dto
    2가지 id와 1가지의 asset_root_path가 생성된다
"""

@dataclass(frozen=True)
class AssetBundleDTO:
    song_id : str
    asset_id: str
    result_id: str
    asset_root_path: str

    audio_original_path: str | None
    audio_bass_only_path: str | None
    audio_bass_removed_path: str | None
    audio_bass_boosted_path: str | None

    tab_original_path: str | None
    tab_root_path: str | None