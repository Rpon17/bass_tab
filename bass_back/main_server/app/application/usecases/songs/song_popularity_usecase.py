from dataclasses import dataclass

from bass_back.main_server.app.application.ports.song_repository_port import SongRepository

# 인기도 올리는
@dataclass(frozen=True)
class SelectedPopularitySongUseCase:
    song_repo: SongRepository

    async def execute(self, *, song_id: str) -> None:
        await self.song_repo.increment_select_count(song_id=song_id)
