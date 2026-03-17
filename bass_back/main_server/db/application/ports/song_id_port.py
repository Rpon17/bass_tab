# main_server/app/application/ports/song_repository_port.py
from __future__ import annotations

from typing import Protocol

from app.domain.songs_domain import Song


class SongRepositoryPort(Protocol):
    async def get_by_song_id(self, *, song_id: str) -> Song | None:
        ...

    async def get_by_norm(
        self,
        *,
        norm_title: str,
        norm_artist: str,
    ) -> Song | None:
        ...

    async def search_by_norm_title_prefix(
        self,
        *,
        norm_title_prefix: str,
        limit: int = 10,
    ) -> list[Song]:
        ...

    async def save(self, *, song: Song) -> None:
        ...