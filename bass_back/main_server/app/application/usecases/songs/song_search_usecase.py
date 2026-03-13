# main_server/app/application/usecases/songs/search_songs_usecase.py
from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.song_repository_port import SongRepositoryPort
from app.application.services.text_normalize import normalize_text
from app.domain.songs_domain import Song


@dataclass(frozen=True)
class SearchSongsUseCase:
    song_repository: SongRepositoryPort

    async def execute(
        self,
        *,
        query: str,
        limit: int = 10,
    ) -> list[Song]:
        raw_query: str = query.strip()
        if len(raw_query) == 0:
            return []

        norm_query: str = normalize_text(raw_query)
        if len(norm_query) == 0:
            return []

        limit_: int = int(limit)
        if limit_ <= 0:
            return []

        songs: list[Song] = await self.song_repository.search_by_norm_title_prefix(
            norm_title_prefix=norm_query,
            limit=limit_,
        )
        return songs