from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.domain.results_domain import Result


@dataclass(frozen=True)
class CreateResultUseCase:
    result_repository: ResultRepositoryPort

    async def execute(
        self,
        *,
        song_id: str,
        source_url: str,
    ) -> Result:
        result: Result = Result.create(
            result_id=uuid.uuid4().hex,
            song_id=song_id,
            source_url=source_url,
            status="linked",
        )

        await self.result_repository.save(result=result)
        return result