from __future__ import annotations

from typing import Protocol

from app.domain.results_domain import Result


class ResultRepositoryPort(Protocol):
    async def get_by_result_id(self, *, result_id: str) -> Result | None:
        ...

    async def save(self, *, result: Result) -> None:
        ...