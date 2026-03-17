from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Path, status

from app.api.v1.dto.songs_dto import SongListItemDTO, CreateSongRequest, CreateSongResponse
from app.api.v1.deps import get_search_songs_uc

from app.application.usecases.songs.song_create_usecase import CreateSongUseCase
from app.application.usecases.songs.song_search_usecase import SearchSongsUseCase


router = APIRouter(prefix="/songs", tags=["songs"])


@router.get("/search")
async def search_songs(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=20),
    usecase: SearchSongsUseCase = Depends(get_search_songs_uc),
) -> list[dict[str, str]]:
    songs = await usecase.execute(
        query=q,
        limit=limit,
    )
    return [
        {
            "song_id": song.song_id,
            "title": song.title,
            "artist": song.artist,
        }
        for song in songs
    ]