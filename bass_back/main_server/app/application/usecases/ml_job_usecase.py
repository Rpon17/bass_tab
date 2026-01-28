from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.domain.jobs_domain import JobStatus  # 네 프로젝트 enum 위치에 맞춰
from app.application.ports.job_store_port import JobStore
from app.application.ports.ml_client_port import MLClientPort, Mode


@dataclass(frozen=True)
class ProcessJobUseCase:
    job_store: JobStore
    ml_client: MLClientPort

    async def execute(
        self,
        *,
        job_id: str,
        mode: Mode = "full",
    ) -> None:
        # 일단 job을 로드함
        job = await self.job_store.get(job_id)
        if job is None:
            # 큐에 있는데 job이 없으면 데이터 정합성 문제 → 그냥 스킵
            return

        # 2) submitted 전이
        job.status = JobStatus.SUBMITTED
        await self.job_store.save(job)

        try:
            # ml_server로 보낼 입력을 준비함
            # 워커가 만든 input_wav_path에 실제로 파일이 있는지 확인
            if not job.input_wav_path:
                raise ValueError("job.input_wav_path is missing")

            # ml_server로 보낼 포트를 호출함 이 프로세스정보를 저장함
            resp = await self.ml_client.process(
                job_id=job_id,
                input_wav_path=job.input_wav_path,
                mode=mode,
                meta=getattr(job, "meta", None) or {},
            )
            
            # 만약 resp가 ok가 아니거나 result가 비어있다면 error를 띄움
            if not resp.ok or resp.result is None:
                raise RuntimeError(resp.error or "ML processing failed (no error message)")

            # 5) done 전이 + 결과 저장
            job.status = JobStatus.DONE
            job.result_path = resp.result.bass_wav_path  # 네 도메인 필드명에 맞춰
            # notes/bpm/tabs를 job에 저장할지, 별도 결과 파일로 저장할지는 선택인데
            # 우선 job.meta에 넣어도 됨
            if hasattr(job, "meta") and isinstance(job.meta, dict):
                job.meta["bpm"] = resp.result.bpm
                job.meta["notes"] = resp.result.notes
                job.meta["tabs"] = resp.result.tabs

            await self.job_store.save(job)

        except Exception as e:
            # 6) failed 전이
            job.status = JobStatus.FAILED
            job.error = str(e) if hasattr(job, "error") else None
            await self.job_store.save(job)
