from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


# 요청받는 dto
@dataclass(frozen=True)
class AudioPreprocessRequestPort:
    input_wav_path: Path
    output_dir: Path
    asset_id: str = None

    # 튜닝 파라미터 (기본값은 네 요구에 맞춤)
    highpass_hz: float = 40.0
    lowpass_hz: float = 5000.0


# 내보내는 dto
@dataclass(frozen=True)
class AudioPreprocessResultPort:
    preprocessed_wav_path: Path


# 결과적으로 이게 포트
class AudioPreprocessUseCasePort(ABC):
    @abstractmethod
    async def preprocess_and_save(
        self,
        *,
        req: AudioPreprocessRequestPort,
    ) -> AudioPreprocessResultPort:
        ...
