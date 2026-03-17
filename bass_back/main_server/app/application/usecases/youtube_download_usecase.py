from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.application.ports.job_store_port import JobStore
from app.application.ports.youtube_download_port import YoutubeAudioDownload


@dataclass(frozen=True)
class DownloadYoutubeAudioUseCase:
    job_store: JobStore
    downloader: YoutubeAudioDownload

    async def run(self, *, job_id: str, url: str, output_path: Path) -> Path:
        token: str = uuid.uuid4().hex

        print("[youtube_download_uc] run 시작")
        print(f"[youtube_download_uc] job_id={job_id}")
        print(f"[youtube_download_uc] url={url}")
        print(f"[youtube_download_uc] output_path={output_path}")
        print(f"[youtube_download_uc] token={token}")

        locked: bool = await self.job_store.acquire_lock(
            job_id,
            token=token,
            ttl_seconds=60 * 10,
        )
        print(f"[youtube_download_uc] lock acquired={locked}")

        if not locked:
            print("[youtube_download_uc] lock 획득 실패 -> output_path 반환")
            print(f"[youtube_download_uc] output_path exists={output_path.exists()}")
            return output_path

        try:
            print("[youtube_download_uc] job 조회 시작")
            job = await self.job_store.get(job_id)
            print(f"[youtube_download_uc] job 조회 결과 is_none={job is None}")

            if job is None:
                raise ValueError(f"Job not found: {job_id}")

            print("[youtube_download_uc] mark_submitted 시작")
            print(f"[youtube_download_uc] before submitted job.status={job.status}")
            job.mark_submitted()
            print(f"[youtube_download_uc] after submitted job.status={job.status}")

            await self.job_store.save(job, ttl_seconds=60 * 30)
            print("[youtube_download_uc] submitted save 완료")

            print("[youtube_download_uc] downloader.download_wav 시작")
            produced_path: Path = await self.downloader.download_wav(
                url,
                output_path=output_path,
            )
            print("[youtube_download_uc] downloader.download_wav 완료")
            print(f"[youtube_download_uc] produced_path={produced_path}")
            print(f"[youtube_download_uc] produced_path exists={produced_path.exists()}")

            print("[youtube_download_uc] mark_done 시작")
            print(f"[youtube_download_uc] before done job.status={job.status}")
            job.mark_done(result_path=str(produced_path))
            print(f"[youtube_download_uc] after done job.status={job.status}")
            print(f"[youtube_download_uc] job.result_path={job.result_path}")

            await self.job_store.save(job, ttl_seconds=60 * 30)
            print("[youtube_download_uc] done save 완료")

            print("[youtube_download_uc] run 정상 종료")
            return produced_path

        except Exception as e:
            print("[youtube_download_uc] 예외 발생")
            print(f"[youtube_download_uc] exception type={type(e).__name__}")
            print(f"[youtube_download_uc] exception={e}")

            job = await self.job_store.get(job_id)
            print(f"[youtube_download_uc] except job reload is_none={job is None}")

            if job is not None:
                print(f"[youtube_download_uc] before failed job.status={job.status}")
                job.mark_failed(error=f"{type(e).__name__}: {e}")
                print(f"[youtube_download_uc] after failed job.status={job.status}")
                print(f"[youtube_download_uc] job.error={job.error}")

                await self.job_store.save(job, ttl_seconds=60 * 30)
                print("[youtube_download_uc] failed save 완료")

            raise

        finally:
            print("[youtube_download_uc] lock release 시작")
            released: bool = await self.job_store.release_lock(job_id, token=token)
            print(f"[youtube_download_uc] lock release 완료 released={released}")