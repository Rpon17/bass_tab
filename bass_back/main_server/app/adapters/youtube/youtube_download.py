# adapters/youtube/yt_dlp_downloader.py
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from yt_dlp import YoutubeDL

from bass_back.main_server.app.application.ports.youtube_download import YoutubeAudioDownload


def _download_youtube_audio_sync(url: str, *, output_path: Path) -> Path:
    """
    - url = 실제로 다운로드할 유튜브 음원 url
    - output_path: 최종 wav가 저장될 경로
    - return: 실제 생성된 wav 경로
    """
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # 일단 기본적으로 확장자를 없애고 감
    outtmpl_base = output_path.with_suffix("")

    # ydl_opts 어떤 기준으로 다운할거냐에대한 설명
    ydl_opts = {
        # 최고음질
        "format": "bestaudio/best",
        
        # 다운로드 파일명 템플릿
        "outtmpl": str(outtmpl_base),

        # 콘솔에 뭐 출력하지 마라
        "quiet": True,
        "no_warnings": True,

        # 재시도/네트워크 안정성 옵션
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,

        # 영상 후처리 목록
        # ffmeg로 오디오를 추출하되 wav로 저장하며 최고품질로 해라
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0", 
            }
        ],
    }

    # 여긴 비동기가 안됨
    with YoutubeDL(ydl_opts) as ydl:
        """
            저 url을 ydl_opts라는 기준으로 다운로드 하는디 .wav확장자를 붙인다 
        """
        ydl.download([url])
    produced = outtmpl_base.with_suffix(".wav")
    return produced


class YtDlpYoutubeAudioDownloader(YoutubeAudioDownload):
    """
        이 모든거를 하나로 모은 클래스
        이거를 down_wav로 한줄로 정리함
        그리고 이단계에서 비동기스레드로 옮겨버림
        비동기 스레드에서는 
        _download_youtube_audio_sync,
            url,
            output_path=output_path,
        이 정보들을 가지고 스레드에서 실행하고 결과 path를 return 해줌
    """

    async def download_wav(self, url: str, *, output_path: Path) -> Path:
        return await asyncio.to_thread(
            _download_youtube_audio_sync,
            url,
            output_path=output_path,
        )
