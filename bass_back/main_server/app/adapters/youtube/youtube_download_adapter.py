from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from app.application.ports.youtube_download_port import YoutubeAudioDownload


def _progress_hook(d: dict[str, Any]) -> None:
    """
    yt-dlp 진행 로그 (필요한 것만 출력)
    """
    status: str = str(d.get("status", ""))
    if status == "downloading":
        downloaded: Any = d.get("downloaded_bytes")
        total: Any = d.get("total_bytes") or d.get("total_bytes_estimate")
        speed: Any = d.get("speed")
        eta: Any = d.get("eta")
        print(f"[yt-dlp] downloading: downloaded={downloaded} total={total} speed={speed} eta={eta}")
    elif status == "finished":
        filename: str = str(d.get("filename", ""))
        print(f"[yt-dlp] finished download: {filename}")


def _sanitize_for_json(value: Any) -> Any:
    """
    json.dumps로 출력 가능한 형태로 변환한다.
    - callable(함수/메서드)는 문자열로 치환
    - dict/list/tuple은 재귀적으로 처리
    - 그 외 json 불가 타입은 repr로 치환
    """
    if callable(value):
        name: str = getattr(value, "__name__", type(value).__name__)
        return f"<callable {name}>"

    if isinstance(value, (bytes, bytearray)):
        return value.decode(errors="replace")

    if isinstance(value, dict):
        return {str(k): _sanitize_for_json(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_sanitize_for_json(v) for v in value]

    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def _download_youtube_audio_sync(
    url: str,
    *,
    output_path: Path,
    debug: bool = True,
    cookies_path: Path | None = None,
) -> Path:
    """
    yt-dlp + ffmpeg로 유튜브 오디오를 WAV로 추출하는 동기 함수.
    - yt-dlp는 동기 API이므로 async에서는 to_thread로 감싼다.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # yt-dlp는 outtmpl을 확장자 없는 base로 주고, postprocessor가 확장자를 붙인다.
    outtmpl_base: Path = output_path.with_suffix("")

    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(outtmpl_base),
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "quiet": not debug,
        "no_warnings": not debug,
        "verbose": debug,
        "progress_hooks": [_progress_hook],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
    }

    if cookies_path is not None:
        print("[yt-dlp] using cookiefile:", str(cookies_path))
        ydl_opts["cookiefile"] = str(cookies_path)

    if debug:
        safe_opts: dict[str, Any] = dict(ydl_opts)
        if "cookiefile" in safe_opts:
            safe_opts["cookiefile"] = "<cookiefile>"

        safe_opts_jsonable: Any = _sanitize_for_json(safe_opts)

        print("[yt-dlp] url =", url)
        print("[yt-dlp] output_path =", str(output_path))
        print("[yt-dlp] outtmpl_base =", str(outtmpl_base))
        print("[yt-dlp] ydl_opts =", json.dumps(safe_opts_jsonable, ensure_ascii=False, indent=2))

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    produced: Path = outtmpl_base.with_suffix(".wav")

    print("[yt-dlp] expected produced wav:", str(produced))
    print("[yt-dlp] produced exists:", produced.exists())

    if not produced.exists():
        raise FileNotFoundError(f"wav not found after yt-dlp download: {produced}")

    return produced


@dataclass(frozen=True)
class YtDlpYoutubeAudioDownloader(YoutubeAudioDownload):
    """
    Adapter (Port 구현체)
    - Port: YoutubeAudioDownload
    - Impl: yt-dlp(동기) + asyncio.to_thread로 비동기 호환
    """
    debug: bool = True
    cookies_path: Path | None = None

    async def download_wav(self, url: str, *, output_path: Path) -> Path:
        return await asyncio.to_thread(
            _download_youtube_audio_sync,
            url,
            output_path=output_path,
            debug=self.debug,
            cookies_path=self.cookies_path,
        )