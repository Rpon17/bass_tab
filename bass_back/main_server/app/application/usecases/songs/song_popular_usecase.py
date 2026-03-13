from __future__ import annotations

from dataclasses import dataclass

from bass_back.main_server.app.application.ports.song_repository_port import SongRepository
from app.domain.songs_domain import Song

# 홈 화면에서 인기곡 띄우는
@dataclass(frozen=True)
class GetPopularSongsUseCase:
    song_repo: SongRepository

    async def execute(self, *, limit: int = 10) -> list[Song]:
        """
        홈 화면 인기곡 조회.
        - 정렬 기준은 Repo가 책임짐(select_count DESC, updated_at DESC)
        - limit 검증은 Repo에서 이미 하고 있어도, 여기서 한 번 더 해도 됨
        """
        limit_: int = int(limit)
        if limit_ <= 0:
            return []
        return await self.song_repo.get_popular(limit=limit_)