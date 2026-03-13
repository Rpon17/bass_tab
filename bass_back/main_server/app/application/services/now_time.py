from datetime import datetime, timezone

# 현재시간을 문자열로 반환
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")