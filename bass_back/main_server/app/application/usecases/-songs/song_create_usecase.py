from __future__ import annotations

from dataclasses import dataclass
import uuid

from bass_back.main_server.app.application.ports.song_repository_port import SongRepositoryPort
from app.application.services.text_normalize import normalize_text
from app.domain.songs_domain import Song

"""  
    DB : song관련 정보 저장
    song_id를 생성하며 여기서 
    song과 관련된 정보들을 저장함
    song_id      
    title       
    artist       
    norm_title   
    norm_artist  
    created_at   
    updated_at 
    는 여기서 저장
"""
@dataclass(frozen=True)
class CreateSongUseCase:
    song_repo: SongRepositoryPort

    async def execute(
        self,
        *,
        title: str,
        artist: str,
    ) -> Song:
        raw_title: str = title.strip()
        raw_artist: str = artist.strip()
        
        # 공백제거했는데 0 x
        if len(raw_title) == 0 or len(raw_artist) == 0:
            raise ValueError("title/artist must not be empty")
        
        # 정규화했는데 0 x
        norm_title: str = normalize_text(raw_title)
        norm_artist: str = normalize_text(raw_artist)
        if len(norm_title) == 0 or len(norm_artist) == 0:
            raise ValueError("normalized title/artist must not be empty")

        # 완벽히 같은게 있다면
        existing: Song | None = await self.song_repo.completely_same(
            norm_title=norm_title,
            norm_artist=norm_artist,
        )
        
        # 만약 완벽히 같은게 없다면 그대로 감
        if existing is not None:
            return existing

        song_id: str = uuid.uuid4().hex

        # song_repo에 이거를 기준으로 하나 repo를 만든다
        creating: Song = await self.song_repo.create(
            song_id=song_id,
            title=raw_title,
            artist=raw_artist,
            norm_title=norm_title,
            norm_artist=norm_artist,
        )
        return creating
