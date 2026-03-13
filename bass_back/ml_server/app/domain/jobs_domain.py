from __future__ import annotations

from enum import Enum

    
# 상태 변경
class MLJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

class DownLoadType(str, Enum):
    AUDIO = "audio"
    Tab = "tab"
    
class DetailType(str, Enum):
    ORIGINAL = "original"
    BASS_ONLY = "bass_only"
    BASS_REMOVED = "bass_removed"
    BASS_BOOSTED = "bass_boosted"


