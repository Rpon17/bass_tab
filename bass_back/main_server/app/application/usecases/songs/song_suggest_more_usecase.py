from __future__ import annotations

from dataclasses import dataclass

from app.domain.songs_domain import Song
from bass_back.main_server.app.application.ports.song_repository_port import SongRepository
from app.application.services.text_normalize import normalize_text

# 이건 엔터눌렀을때 %prefix%버전 
@dataclass(frozen=True)
class SuggestMoreSongsUseCase:
    song_repo: SongRepository

    async def execute(self, *, q: str, limit: int = 10) -> list[Song]:
        q_norm: str = normalize_text(q)
        if not q_norm:
            return []
        limit_: int = int(limit)
        if limit_ <= 0:
            return []
        return await self.song_repo.more_suggest(q_norm=q_norm, limit=limit_)
