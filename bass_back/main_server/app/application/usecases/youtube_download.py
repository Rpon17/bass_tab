# application/usecases/youtube_download.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from application.ports.job_store import JobStore
from bass_back.main_server.app.application.ports.youtube_download import YoutubeAudioDownload


@dataclass(frozen=True)
class DownloadYoutubeAudioUseCase:
    """
    ✅ 유튜브 오디오 다운로드 UseCase
    - 책임: job 생성/상태관리 + 락 획득 + 어댑터(yt-dlp) 호출 + 결과 저장
    - 실제 기술(yt-dlp/redis)은 포트를 통해 주입받음
    """
    job_store: JobStore
    downloader: YoutubeAudioDownload

    async def enqueue(self, *, url: str) -> str:
        """
        ✅ '작업 등록' 역할
        - job_id 만들고 JobStore에 queued로 저장
        - API는 여기서 job_id만 받으면 됨
        """
        job_id = uuid.uuid4().hex
        await self.job_store.create_job(
            job_id,
            meta={"url": url},
            ttl_seconds=60 * 30,
        )
        return job_id

    async def run(self, *, job_id: str, url: str, output_path: Path) -> Path:
        """
        ✅ 워커가 실제 실행할 메서드
        - 락으로 중복 실행 방지
        - 성공/실패 상태 기록
        - 결과(result)에 output_path 등 저장
        """
        token = uuid.uuid4().hex

        # 1) 락 획득(원자적 확인+획득)
        locked = await self.job_store.acquire_lock(job_id, token=token, ttl_seconds=60 * 10)
        if not locked:
            # 이미 다른 워커가 처리 중이거나, 직전에 처리 중
            # 여기서 예외를 던질지, 그냥 리턴할지는 정책 문제
            # 지금은 "조용히 종료"로 둠
            return output_path

        try:
            # 2) running 상태로 변경
            await self.job_store.set_running(job_id)
            await self.job_store.set_progress(job_id, progress=0.05)

            # 3) 다운로드 수행
            produced_path = await self.downloader.download_wav(url, output_path=output_path)
            await self.job_store.set_progress(job_id, progress=0.90)

            # 4) 성공 기록
            result: Dict[str, Any] = {
                "audio_wav_path": str(produced_path),
            }
            await self.job_store.set_succeeded(job_id, result=result)
            return produced_path

        except Exception as e:
            # 5) 실패 기록
            await self.job_store.set_failed(job_id, error=f"{type(e).__name__}: {e}")
            raise

        finally:
            # 6) 락 해제
            await self.job_store.release_lock(job_id, token=token)
