from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.domain.results_domain import Result

from app.domain.jobs_domain import Job

@dataclass(frozen=True)
class CreateResultUseCase:
    result_repository: ResultRepositoryPort


    async def execute(self, *,result_id: str, song_id: str, source_url: str) -> Result:
        print(f"!!! [STEP 1] Result 생성 시작: song_id={song_id}", flush=True)
        
        result: Result = Result.create(
            result_id=result_id,
            song_id=song_id,
            source_url=source_url,
            status="queued", 
        )
        
        print(f"!!! [STEP 2] DB 저장 직전: result_id={result.result_id}", flush=True)
        
        try:
            await self.result_repository.save(result=result)
            print("!!! [STEP 3] DB 저장 함수 호출 완료 (성공 로그 아님)", flush=True)
        except Exception as e:
            print(f"!!! [DB ERROR] 저장 중 예외 발생: {e}", flush=True)
            raise e

        print("!!! [STEP 4] 유스케이스 종료 직전", flush=True)
        return result