import sqlite3
from dataclasses import dataclass
from app.application.ports.front_back_port import FrontBackRepositoryPort

@dataclass(frozen=True)
class FrontBackSqliteAdapter(FrontBackRepositoryPort):
    db_path: str

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def search_songs_with_results(self, *, query: str, limit: int = 10) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                    SELECT 
                        s.song_id, 
                        s.title, 
                        s.artist,
                        r.result_id, 
                        r.status,   
                        a.asset_id,
                        a.original_audio_path, 
                        a.bass_only_path, 
                        a.bass_removed_path, 
                        a.bass_boosted_path,
                        a.original_tab_path, 
                        a.root_tab_path
                    FROM songs s
                    LEFT JOIN results r ON s.song_id = r.song_id
                    LEFT JOIN assets a ON r.result_id = a.result_id  -- result를 통해 asset과 연결
                    WHERE s.title LIKE ? OR s.artist LIKE ?
                    ORDER BY s.select_count DESC, s.updated_at DESC  -- 인기순/최신순 정렬
                    LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()