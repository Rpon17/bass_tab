# application/usecases/youtube_download.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from bass_back.main_server.app.application.ports.job_store_port import JobStore
from bass_back.main_server.app.application.ports.youtube_download_port import YoutubeAudioDownload

"""
    jobstor 포트와 youtube download 포트 에서 정보들을 가져옴
    이 정보들은 여기에는 job_id url out_path만 있으면 됨
    토큰은 
"""
@dataclass(frozen=True)
class DownloadYoutubeAudioUseCase:
    job_store: JobStore
    downloader: YoutubeAudioDownload

    async def run(self, *, job_id: str, url: str, output_path: Path) -> Path:
        token = uuid.uuid4().hex

        locked = await self.job_store.acquire_lock(job_id, token=token, ttl_seconds=60 * 10)
        if not locked:
            return output_path

        try:
            # 1) Job 조회 (없으면 에러)
            job = await self.job_store.get(job_id)
            if job is None:
                raise ValueError(f"Job not found: {job_id}")

            # 2) running 전이 + 저장
            job.mark_running()
            await self.job_store.save(job, ttl_seconds=60 * 30)

            # 3) 실제 다운로드
            produced_path = await self.downloader.download_wav(url, output_path=output_path)

            # 4) 성공 전이 + 결과 저장 (도메인 필드에 맞춰 저장)
            job.mark_done(result_path=str(produced_path))
            await self.job_store.save(job, ttl_seconds=60 * 30)

            return produced_path

        except Exception as e:
            # 실패 전이 + 저장
            job = await self.job_store.get(job_id)
            if job is not None:
                job.mark_failed(error=f"{type(e).__name__}: {e}")
                await self.job_store.save(job, ttl_seconds=60 * 30)
            raise

        finally:
            await self.job_store.release_lock(job_id, token=token)
