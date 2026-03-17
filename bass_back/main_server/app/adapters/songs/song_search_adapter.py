import sqlite3
import asyncio
from app.domain.songs_domain import Song
from app.application.ports.song_repository_port import SongRepositoryPort

class SqliteSongRepository(SongRepositoryPort):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    async def search_by_norm_title_prefix(self, *, norm_title_prefix: str, limit: int = 10) -> list[Song]:
        def _execute():
            conn = self._connect()
            try:
                # norm_title이 norm_title_prefix로 시작하는 곡들을 검색
                cursor = conn.execute(
                    "SELECT song_id, title, artist, norm_title, norm_artist FROM songs WHERE norm_title LIKE ? LIMIT ?",
                    (f"{norm_title_prefix}%", limit)
                )
                rows = cursor.fetchall()
                return [Song(song_id=r[0], title=r[1], artist=r[2], norm_title=r[3], norm_artist=r[4]) for r in rows]
            finally:
                conn.close()
        
        return await asyncio.to_thread(_execute)
    
    # ... 나머지 메서드(save, get_by_song_id 등)도 여기서 구현해야 합니다.