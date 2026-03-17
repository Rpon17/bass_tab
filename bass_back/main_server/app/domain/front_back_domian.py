# app/domain/models/result.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class FrontBackDTO:
    result_id: str
    song_id: str
    asset_id: str
    
    original_audio_path: str
    bass_only_path: str
    bass_removed_path: str
    bass_boosted_path: str
    
    original_tab_path: str
    root_tab_path: str