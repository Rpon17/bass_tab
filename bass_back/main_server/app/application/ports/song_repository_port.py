# main_server/app/application/ports/song_repository_port.py
from __future__ import annotations

from typing import Protocol

from app.domain.songs_domain import Song


class SongRepositoryPort(Protocol):
    
    # song_id로 곡을 찾는다
    async def get_by_song_id(self, *, song_id: str) -> Song | None:
        ...

    # norm_title로 같은 곡이 db에 있는지 찾아봄
    async def get_by_norm(
        self,
        *,
        norm_title: str,
        norm_artist: str,
    ) -> Song | None:
        ...

    # 검색 버튼용 *norm* 가 들어오면 songlist에서 찾아줌
    async def search_by_norm_title_prefix(
        self,
        *,
        norm_title_prefix: str,
        limit: int = 10,
    ) -> list[Song]:
        ...

    # 저장함
    async def save(self, *, song: Song) -> None:
        ...