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
    song_repository: SongRepositoryPort

    async def execute(
        self,
        *,
        title: str,
        artist: str,
    ) -> Song:
        norm_title : str = normalize_text(title)
        norm_artist : str = normalize_text(artist)
        existing: Song | None = await self.song_repository.get_by_norm(
            norm_title=norm_title,
            norm_artist=norm_artist,
        )
        if existing is not None:
            return existing

        song: Song = Song.create(
            song_id=uuid.uuid4().hex,
            title=title,
            artist=artist,
            norm_title=norm_title,
            norm_artist=norm_artist,
        )

        await self.song_repository.save(song=song)
        return song