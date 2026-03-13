# main_server/app/domain/songs_domain.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Song:
    song_id: str
    title: str
    artist: str
    norm_title: str
    norm_artist: str
    created_at: str
    updated_at: str
    select_count: int = 0

    @classmethod
    def create(
        cls,
        *,
        song_id: str,
        title: str,
        artist: str,
        norm_title: str,
        norm_artist: str,
    ) -> "Song":
        now: str = utc_now_iso()
        return cls(
            song_id=song_id,
            title=title,
            artist=artist,
            norm_title=norm_title,
            norm_artist=norm_artist,
            created_at=now,
            updated_at=now,
            select_count=0,
        )