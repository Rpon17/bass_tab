from __future__ import annotations

from pydantic import BaseModel, Field


class AssetListItemDTO(BaseModel):
    result_id: str
    song_id: str
    source_url: str
    status: str | None = None


class CreateAssetRequest(BaseModel):
    youtube_url: str = Field(..., min_length=1, max_length=500)
    title: str = Field(..., min_length=1, max_length=200)
    artist: str = Field(..., min_length=1, max_length=200)


class CreateAssetResponse(BaseModel):
    result_id: str
    song_id: str