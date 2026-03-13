from __future__ import annotations

from pydantic import BaseModel,  Field


class SongListItemDTO(BaseModel):
    song_id: str
    title: str
    artist: str
    select_count: int | None = None


class CreateSongRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    artist: str = Field(..., min_length=1, max_length=200)


class CreateSongResponse(BaseModel):
    song_id: str
    title: str
    artist: str