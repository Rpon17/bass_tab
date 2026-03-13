from __future__ import annotations

from dataclasses import dataclass, field

from app.application.services.now_time import utc_now_iso


@dataclass(frozen=True)
class Result:
    result_id: str
    song_id: str
    source_url: str
    status: str = "linked"
    error_message: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        *,
        result_id: str,
        song_id: str,
        source_url: str,
        status: str = "linked",
        error_message: str | None = None,
    ) -> "Result":
        now: str = utc_now_iso()
        return cls(
            result_id=result_id,
            song_id=song_id,
            source_url=source_url,
            status=status,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )