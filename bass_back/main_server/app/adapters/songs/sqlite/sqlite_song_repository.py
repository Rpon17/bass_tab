from __future__ import annotations

import asyncio
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from app.domain.songs_domain import Song
from app.application.services.text_normalize import normalize_text
from app.adapters.songs.sqlite.sqlite_connection import SqliteConnectionFactory
from app.application.ports.song_repository_port import SongRepositoryPort
from app.application.services.now_time import utc_now_iso


@dataclass(frozen=True)
class SqliteSongRepository(SongRepositoryPort):
    cx: SqliteConnectionFactory

    # -------------------------
    # row -> song으로 바꾸는 코드
    # row 를 song으로 변환함 = db표현(그저 문자열)을 domain표현으로 변환
    # -------------------------
    def _row_to_song(self, r: Any) -> Song:
        return Song(
            song_id=str(r["song_id"]),
            title=str(r["title"]),
            artist=str(r["artist"]),
            norm_title=str(r["norm_title"]),
            norm_artist=str(r["norm_artist"]),
            select_count=int(r["select_count"]),
            created_at=str(r["created_at"]),
            updated_at=str(r["updated_at"]),
        )

    # -------------------------
    # 인기도 상위 10개 가져오는 명령
    # input -> limit 개수 (몇개 가져올지)
    # -------------------------
    async def get_popular(self, *, limit: int) -> list[Song]:
        limit_: int = int(limit)
        if limit_ <= 0:
            return []

        def _query() -> list[Song]:
            with self.cx.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    FROM songs
                    ORDER BY select_count DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (limit_,),
                ).fetchall()
            return [self._row_to_song(r) for r in rows]

        return await asyncio.to_thread(_query)

    """ 
        검색하면 자동완성 해줌
        q_norm은 이미 정규화된 값
    """

    # -------------------------
    # 검색도주에 0.3초 이상 타자를 안치면 추천노래를 아래에 띄워줌
    # input -> q_norm = 노래제목 limit = 최대 개수
    # q_norm은 여기가 아닌 유스케이스에서 정규화 할것
    # -------------------------
    async def suggest(self, *, q_norm: str, limit: int = 5) -> list[Song]:
        norm_q: str = q_norm.strip()
        if len(norm_q) == 0:
            return []

        limit_: int = int(limit)
        if limit_ <= 0:
            return []

        # prefix는 슬라이싱하는거임 12글자를 커트라인으로
        prefix: str = norm_q[: max(1, min(len(norm_q), 12))]
        like_pattern: str = f"{prefix}%"

        def _query() -> list[Song]:
            with self.cx.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    FROM songs
                    WHERE norm_title LIKE ?
                    ORDER BY select_count DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (like_pattern, limit_),
                ).fetchall()
            return [self._row_to_song(r) for r in rows]

        return await asyncio.to_thread(_query)

    # -------------------------
    # 만약 위에서 찾지 못했다면 중간까지 포함하는 코드
    # input -> limit -> 최대 개수
    # 이 코드는 반드시 suggest를 사용한 이후에 사용 가능하다
    # -------------------------
    async def more_suggest(self, *, q_norm: str, limit: int = 5) -> list[Song]:
        norm_q: str = q_norm.strip()
        if len(norm_q) == 0:
            return []

        limit_: int = int(limit)
        if limit_ <= 0:
            return []

        # ✅ contains 검색은 전체 문자열을 쓰는게 맞음 (기존 prefix 계산 로직 오류)
        like_pattern: str = f"%{norm_q}%"

        def _query() -> list[Song]:
            with self.cx.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    FROM songs
                    WHERE norm_title LIKE ?
                    ORDER BY select_count DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (like_pattern, limit_),
                ).fetchall()
            return [self._row_to_song(r) for r in rows]

        return await asyncio.to_thread(_query)

    # -------------------------
    # 완벽하게 같은음악과 가수가 있는지 확인하는 단계
    # 사실상 중복방지를 목적으로 한다 보면 됨
    # -------------------------
    async def completely_same(self, *, norm_title: str, norm_artist: str) -> Optional[Song]:
        nt: str = norm_title.strip()
        na: str = norm_artist.strip()
        if len(nt) == 0 or len(na) == 0:
            return None

        def _get() -> Optional[Song]:
            with self.cx.connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    FROM songs
                    WHERE norm_title = ?
                      AND norm_artist = ?
                    """,
                    (nt, na),
                ).fetchone()
            return None if row is None else self._row_to_song(row)

        return await asyncio.to_thread(_get)

    # -------------------------
    # 실제로 생성해서 스키마에 추가하는 코드
    # input -> 제목,가수,비슷노래,비슷가수를 넣으면 song_id와 현재시간,nt,na를 만들고 집어넣음
    # -------------------------
    async def create(
        self,
        *,
        song_id: str,
        title: str,
        artist: str,
        norm_title: str,
        norm_artist: str,
    ) -> Song:
        sid: str = song_id.strip()
        if not sid:
            raise ValueError("song_id must not be empty")

        now: str = utc_now_iso()
        nt: str = norm_title.strip()
        na: str = norm_artist.strip()

        def _insert() -> None:
            with self.cx.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO songs (
                        song_id, title, artist, norm_title, norm_artist, created_at, updated_at, select_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (sid, title, artist, nt, na, now, now),
                )
                conn.commit()

        try:
            await asyncio.to_thread(_insert)
        except sqlite3.IntegrityError:
            existing: Optional[Song] = await self.completely_same(norm_title=nt, norm_artist=na)
            if existing is None:
                raise
            return existing

        return Song(
            song_id=sid,
            title=title,
            artist=artist,
            norm_title=nt,
            norm_artist=na,
            select_count=0,
            created_at=now,
            updated_at=now,
        )


    # -------------------------
    # id를 통해서 그 테이블을 가져오는 코드
    # song_id만 input 하면 됨
    # -------------------------
    async def get_by_id(self, *, song_id: str) -> Optional[Song]:
        sid: str = song_id.strip()
        if len(sid) == 0:
            return None

        def _get() -> Optional[Song]:
            with self.cx.connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                        song_id,
                        title,
                        artist,
                        norm_title,
                        norm_artist,
                        created_at,
                        updated_at,
                        select_count
                    FROM songs
                    WHERE song_id = ?
                    """,
                    (sid,),
                ).fetchone()
            return None if row is None else self._row_to_song(row)

        return await asyncio.to_thread(_get)

    # -------------------------
    # 이 코드가 호출될때마다 이 id의 곡의 인기도가 1씩 올라간다
    # song_id만 input 하면 됨
    # -------------------------
    async def increment_select_count(self, *, song_id: str) -> None:
        sid: str = song_id.strip()
        if len(sid) == 0:
            return

        now: str = utc_now_iso()

        def _update() -> None:
            with self.cx.connect() as conn:
                conn.execute(
                    """
                    UPDATE songs
                    SET select_count = select_count + 1,
                        updated_at = ?
                    WHERE song_id = ?
                    """,
                    (now, sid),
                )
                conn.commit()

        await asyncio.to_thread(_update)
"""
    # -------------------------
    # asset_id를 통해서 asset을 가져오는 코드
    # (⚠️ 기존 코드에서 get_by_id 이름이 중복되어 song 조회가 사라지는 버그가 있었음)
    # 그래서 이름을 get_asset_by_id로 분리함
    # -------------------------
    async def get_asset_by_id(self, *, asset_id: str) -> Optional[Asset]:
        aid: str = asset_id.strip()
        if len(aid) == 0:
            return None

        def _get() -> Optional[Asset]:
            with self.cx.connect() as conn:
                row = conn.execute(
                    
                    
                    SELECT
                      asset_id,
                      result_id,
                      storage_path,
                      content_type,
                      kind,
                      variant
                    FROM assets
                    WHERE asset_id = ?
                    ,
                    (aid,),
                ).fetchone()



            if row is None:
                return None

            return Asset(
                asset_id=str(row["asset_id"]),
                result_id=str(row["result_id"]),
                storage_path=str(row["storage_path"]),
                content_type=str(row["content_type"]),
                kind=str(row["kind"]),
                variant=str(row["variant"]),
            )

        return await asyncio.to_thread(_get)
"""