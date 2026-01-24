from __future__ import annotations

import asyncio
from pathlib import Path

from yt_dlp import YoutubeDL

from bass_back.main_server.app.application.ports.youtube_download_port import YoutubeAudioDownload


def _download_youtube_audio_sync(url: str, *, output_path: Path) -> Path:
    """
    yt-dlp + ffmpeg로 유튜브 오디오를 WAV로 추출하는 동기 함수.
    - yt-dlp는 기본적으로 동기 API이므로, async 환경에서는 to_thread로 감싼다.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # yt-dlp는 outtmpl을 확장자 없는 base로 주고, postprocessor가 확장자를 붙인다.
    outtmpl_base = output_path.with_suffix("")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(outtmpl_base),

        "quiet": True,
        "no_warnings": True,

        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    produced = outtmpl_base.with_suffix(".wav")
    return produced


class YtDlpYoutubeAudioDownloader(YoutubeAudioDownload):
    """
    Adapter (Port 구현체)
    - Port: YoutubeAudioDownload
    - Impl: yt-dlp(동기) + asyncio.to_thread로 비동기 호환
    """

    async def download_wav(self, url: str, *, output_path: Path) -> Path:
        return await asyncio.to_thread(
            _download_youtube_audio_sync,
            url,
            output_path=output_path,
        )
