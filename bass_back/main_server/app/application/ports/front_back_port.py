from abc import ABC, abstractmethod
from typing import List
from app.domain.front_back_domian import FrontBackDTO

class FrontBackRepositoryPort(ABC):
    @abstractmethod
    async def search_songs_with_results(self, *, query: str, limit: int = 10) -> list[dict]:
        pass