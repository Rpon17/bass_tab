from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.application.ports import (
    AudioPreprocessRequestPort,
    AudioPreprocessResultPort,
    AudioPreprocessUseCasePort,
)


@dataclass(frozen=True)
class FfmpegAudioPreprocessAdapter(AudioPreprocessUseCasePort):
    """
    전처리 체인:
      - mono 변환
      - high-pass 35~40Hz (기본 40)
      - low-pass 3~5kHz (기본 5000)
      - mild compression
      - normalization

    구현:
      - ffmpeg filtergraph로 처리 후 wav로 저장
      - 만약 특정 필터(acompressor 등)가 빌드에 없어서 실패하면
        dynaudnorm 기반의 fallback 필터로 1회 재시도한다.
    """

    output_filename: str = "normalized_bass_only.wav"

    async def preprocess_and_save(
        self,
        *,
        req: AudioPreprocessRequestPort,
    ) -> AudioPreprocessResultPort:
        input_wav_path: Path = req.input_wav_path
        output_dir: Path = req.output_dir
        asset_id: str = req.asset_id

        if not input_wav_path.exists():
            raise FileNotFoundError(f"input_wav_path not found: {input_wav_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # 필요하면 asset_id 기반으로 하위 폴더를 만들어도 됨 (지금은 output_dir에 바로 저장)
        out_path: Path = output_dir / self.output_filename

        # 1) 기본(권장) 필터: mono + HPF + LPF + mild comp + loudnorm
        # - acompressor: ffmpeg에 있는 경우가 많지만, 환경에 따라 없을 수 있음
        # - loudnorm: 일반적으로 있음(없으면 fallback에서 dynaudnorm 사용)
        primary_filter: str = (
            "aformat=channel_layouts=mono,"
            f"highpass=f={req.highpass_hz},"
            f"lowpass=f={req.lowpass_hz},"
            # mild compression (가능하면 acompressor)
            "acompressor=threshold=-18dB:ratio=2:attack=10:release=120:makeup=4,"
            # normalization
            "loudnorm=I=-16:TP=-1.5:LRA=11"
        )

        # 2) fallback 필터: mono + HPF + LPF + dynaudnorm (대체로 호환성 좋음)
        fallback_filter: str = (
            "aformat=channel_layouts=mono,"
            f"highpass=f={req.highpass_hz},"
            f"lowpass=f={req.lowpass_hz},"
            "dynaudnorm=f=150:g=5"
        )

        try:
            await self._run_ffmpeg(
                input_wav_path=input_wav_path,
                output_wav_path=out_path,
                filtergraph=primary_filter,
            )
        except RuntimeError:
            # primary 실패 시 fallback 1회 재시도
            await self._run_ffmpeg(
                input_wav_path=input_wav_path,
                output_wav_path=out_path,
                filtergraph=fallback_filter,
            )

        if not out_path.exists():
            raise RuntimeError(f"preprocess output not created: {out_path}")

        return AudioPreprocessResultPort(preprocessed_wav_path=out_path)

    async def _run_ffmpeg(
        self,
        *,
        input_wav_path: Path,
        output_wav_path: Path,
        filtergraph: str,
    ) -> None:
        """
        ffmpeg -i input -af <filtergraph> -acodec pcm_s16le -ar 44100 -ac 1 output.wav
        """
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_wav_path),
            "-af",
            filtergraph,
            # wav 표준 PCM
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "1",
            str(output_wav_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_text: str = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg preprocess failed: {err_text}")
