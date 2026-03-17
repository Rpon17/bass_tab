from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class YoutubeAudioDownload(ABC):
    @abstractmethod
    async def download_wav(self, url: str, *, output_path: Path) -> Path:
        ...
