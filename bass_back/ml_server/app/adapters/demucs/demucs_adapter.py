from __future__ import annotations

import asyncio
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.audio import AudioFile
from demucs.pretrained import get_model

from app.application.ports.demucs.demucs_port import (
    DemucsPort,
    DemucsSplitSetting,
    DemucsDspParams,
)

"""  
    demucs에서 분리 -> 4가지 종류의 wav파일 생성 -> bass_only_path return 함
    
    입력 -> original.wav , asset_id , output_dir
    출력 -> path (bass_only)
"""
@dataclass(frozen=True)
class DemucsAdapter(DemucsPort):

    async def split(
        self,
        *,
        input_wav_path: Path,
        asset_id: str,
        output_dir: Path,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> Path:
        return await self.split_full(
            input_wav_path=input_wav_path,
            asset_id=asset_id,
            output_dir=output_dir,
            setting=setting,
            dsp=dsp,
        )

    async def split_file(
        self,
        *,
        input_wav_path: Path,
        output_dir: Path,
        asset_id: str,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> None:
        await self.split_only_bass(
            input_wav_path=input_wav_path,
            output_dir=output_dir,
            asset_id=asset_id,
            setting=setting,
            dsp=dsp,
        )

    async def split_full(
        self,
        *,
        input_wav_path: Path,
        asset_id: str,
        output_dir: Path,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> Path:

        bass_only_path: Path = await self._run_split(
            input_wav_path=input_wav_path,
            output_dir=output_dir,
            asset_id=asset_id,
            mode="full",

            boosted_volume_db=float(setting.boosted_volume_db),
            demucs_model=str(setting.demucs_model),
            overwrite_outputs=bool(setting.overwrite_outputs),
            cleanup_stems=bool(setting.cleanup_stems),
            enable_dsp=bool(dsp.enable_dsp),

            dsp_highpass_hz=float(dsp.dsp_highpass_hz),
            dsp_lowpass_hz=float(dsp.dsp_lowpass_hz),
            dsp_force_mono=bool(dsp.dsp_force_mono),
            dsp_compress=bool(dsp.dsp_compress),
        )
        return bass_only_path

    async def split_only_bass(
        self,
        *,
        input_wav_path: Path,
        output_dir: Path,
        asset_id: str,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> None:
        await self._run_split(
            input_wav_path=input_wav_path,
            output_dir=output_dir,
            asset_id=asset_id,
            mode="bass_only",
            boosted_volume_db=float(setting.boosted_volume_db),
            demucs_model=str(setting.demucs_model),
            overwrite_outputs=bool(setting.overwrite_outputs),
            cleanup_stems=bool(setting.cleanup_stems),
            enable_dsp=bool(dsp.enable_dsp),
            dsp_highpass_hz=float(dsp.dsp_highpass_hz),
            dsp_lowpass_hz=float(dsp.dsp_lowpass_hz),
            dsp_force_mono=bool(dsp.dsp_force_mono),
            dsp_compress=bool(dsp.dsp_compress),
        )

    async def _run_split(
        self,
        *,
        input_wav_path: Path,
        output_dir: Path,
        asset_id: str,
        mode: Literal["bass_only", "full"],
        boosted_volume_db: float,
        demucs_model: str,
        overwrite_outputs: bool,
        cleanup_stems: bool,
        enable_dsp: bool,
        dsp_highpass_hz: float,
        dsp_lowpass_hz: float,
        dsp_force_mono: bool,
        dsp_compress: bool,
    ) -> Path:
        if not input_wav_path.exists():
            raise FileNotFoundError(f"input wav not found: {input_wav_path}")

        if boosted_volume_db < -24.0 or boosted_volume_db > 24.0:
            raise ValueError("too much boosted volume")

        asset_dir: Path = output_dir / "asset" / asset_id
        audio_dir: Path = asset_dir / "audio"
        stem_dir_root: Path = asset_dir / "stem"
        audio_dir.mkdir(parents=True, exist_ok=True)
        stem_dir_root.mkdir(parents=True, exist_ok=True)

        run_id: str = uuid.uuid4().hex
        demucs_tmp_dir: Path = stem_dir_root / f"_demucs_tmp_{run_id}"
        demucs_tmp_dir.mkdir(parents=True, exist_ok=True)

        original_copy: Path = audio_dir / "original.wav"
        bass_only: Path = audio_dir / "bass_only.wav"
        bass_removed: Path = audio_dir / "bass_removed.wav"
        bass_boosted: Path = audio_dir / "bass_boosted.wav"

        required_outputs: list[Path] = (
            [bass_only]
            if mode == "bass_only"
            else [original_copy, bass_only, bass_removed, bass_boosted]
        )

        if not overwrite_outputs:
            for p in required_outputs:
                if p.exists():
                    raise FileExistsError(f"Output already exists: {p}")

        try:
            # full 모드: original.wav 보관
            if mode == "full":
                self._copy_file(
                    input_path=input_wav_path,
                    output_path=original_copy,
                    overwrite=overwrite_outputs,
                )

            # demucs 추론 → stem 임시 저장
            model, samplerate, audio_channels = self._load_model(demucs_model=demucs_model)

            wav: torch.Tensor = self._read_audio(
                input_path=(original_copy if mode == "full" else input_wav_path),
                samplerate=samplerate,
                audio_channels=audio_channels,
            )

            sources: torch.Tensor = self._infer_sources(model=model, wav=wav)

            stem_paths: dict[str, Path] = self._save_stems(
                sources=sources,
                model=model,
                samplerate=samplerate,
                demucs_tmp_dir=demucs_tmp_dir,
            )

            # bass_only 생성 (항상)
            bass_src: Path = self._require_stem(stem_paths=stem_paths, name="bass")
            self._copy_file(
                input_path=bass_src,
                output_path=bass_only,
                overwrite=overwrite_outputs,
            )

            # full 모드에서만 파생 생성
            if mode == "full":
                vocals_src: Path = self._require_stem(stem_paths=stem_paths, name="vocals")
                drums_src: Path = self._require_stem(stem_paths=stem_paths, name="drums")
                other_src: Path = self._require_stem(stem_paths=stem_paths, name="other")

                await self._make_bass_removed(
                    vocals_src=vocals_src,
                    drums_src=drums_src,
                    other_src=other_src,
                    out_path=bass_removed,
                    overwrite=overwrite_outputs,
                )

                await self._make_bass_boosted(
                    bass_removed_path=bass_removed,
                    bass_only_path=bass_only,
                    out_path=bass_boosted,
                    gain_db=boosted_volume_db,
                    overwrite=overwrite_outputs,
                )

            if enable_dsp:
                if mode == "bass_only":
                    await self._dsp_inplace(
                        path=bass_only,
                        dsp_highpass_hz=dsp_highpass_hz,
                        dsp_lowpass_hz=dsp_lowpass_hz,
                        dsp_force_mono=dsp_force_mono,
                        dsp_compress=dsp_compress,
                    )
                else:
                    for p in [bass_only, bass_removed, bass_boosted]:
                        await self._dsp_inplace(
                            path=p,
                            dsp_highpass_hz=dsp_highpass_hz,
                            dsp_lowpass_hz=dsp_lowpass_hz,
                            dsp_force_mono=dsp_force_mono,
                            dsp_compress=dsp_compress,
                        )

        finally:
            if cleanup_stems:
                shutil.rmtree(demucs_tmp_dir, ignore_errors=True)

        print("demucs분리작업 완료")
        return bass_only

    # stem 파일 -> 실제 저장경로
    def _copy_file(self, *, input_path: Path, output_path: Path, overwrite: bool) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and overwrite:
            output_path.unlink()
        shutil.copyfile(str(input_path), str(output_path))

    """  
        1) _load_model()
        ↓
        2) _read_audio()
        ↓
        3) apply_model()
        ↓
        4) stem 분리
    """

    # 모델 로드하는 코드
    def _load_model(self, *, demucs_model: str) -> tuple[object, int, int]:
        model: object = get_model(name=str(demucs_model))
        # type: ignore[attr-defined]
        model.cpu()  # type: ignore[union-attr]
        model.eval()  # type: ignore[union-attr]
        samplerate: int = int(getattr(model, "samplerate", 44100))
        audio_channels: int = int(getattr(model, "audio_channels", 2))
        return model, samplerate, audio_channels

    # wav파일을 demucs가 추론가능한 형태로 읽어옴
    def _read_audio(self, *, input_path: Path, samplerate: int, audio_channels: int) -> torch.Tensor:
        wav: torch.Tensor = AudioFile(str(input_path)).read(
            samplerate=int(samplerate),
            channels=int(audio_channels),
        )
        return self._ensure_batched_wav(wav=wav)

    #
    def _infer_sources(self, *, model: object, wav: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            sources: torch.Tensor = apply_model(
                model,  # type: ignore[arg-type]
                wav,
                device="cpu",
                shifts=2,
                split=True,
                overlap=0.5,
                progress=False,
            )
        return self._ensure_sources_3d(sources=sources)

    def _save_stems(
        self,
        *,
        sources: torch.Tensor,
        model: object,
        samplerate: int,
        demucs_tmp_dir: Path,
    ) -> dict[str, Path]:
        stem_names: list[str] = list(getattr(model, "sources", []))
        if not stem_names:
            raise RuntimeError("Demucs model.sources is empty; cannot map stems.")
        if int(sources.size(0)) != len(stem_names):
            raise RuntimeError(
                f"Unexpected sources shape. got={tuple(sources.shape)} sources={stem_names}"
            )

        stem_paths: dict[str, Path] = {}
        for i, name in enumerate(stem_names):
            stem_path: Path = demucs_tmp_dir / f"{name}.wav"
            self._write_wav(path=stem_path, audio=sources[i], samplerate=int(samplerate))
            stem_paths[name] = stem_path

        return stem_paths

    def _require_stem(self, *, stem_paths: dict[str, Path], name: str) -> Path:
        p: Path | None = stem_paths.get(name)
        if p is None:
            raise RuntimeError(f"Demucs stem missing: {name}. got={list(stem_paths.keys())}")
        return p

    async def _make_bass_removed(
        self,
        *,
        vocals_src: Path,
        drums_src: Path,
        other_src: Path,
        out_path: Path,
        overwrite: bool,
    ) -> None:
        if out_path.exists() and overwrite:
            out_path.unlink()
        await self._mix_many(
            input_paths=[vocals_src, drums_src, other_src],
            output_path=out_path,
        )

    async def _make_bass_boosted(
        self,
        *,
        bass_removed_path: Path,
        bass_only_path: Path,
        out_path: Path,
        gain_db: float,
        overwrite: bool,
    ) -> None:
        if out_path.exists() and overwrite:
            out_path.unlink()
        await self._mix_boost(
            input_path_first=bass_removed_path,
            input_path_second=bass_only_path,
            output_path=out_path,
            gain_db=float(gain_db),
        )

    """  
        audlifile -> 2차원
        demucs -> 3차원
        
    """
    # 2차원이라면 3차원으로 만듬 (전처리)
    def _ensure_batched_wav(self, *, wav: torch.Tensor) -> torch.Tensor:
        if wav.dim() == 2:
            return wav.unsqueeze(0)
        if wav.dim() == 3:
            return wav
        raise RuntimeError(f"Unexpected wav shape from AudioFile.read: {tuple(wav.shape)}")

    # 4차원도 3차원으로 만듬 (후처리)
    def _ensure_sources_3d(self, *, sources: torch.Tensor) -> torch.Tensor:
        if sources.dim() == 4:
            return sources[0]
        if sources.dim() == 3:
            return sources
        raise RuntimeError(f"Unexpected sources shape: {tuple(sources.shape)}")

    # 실제 wav파일로 저장하는 함수
    def _write_wav(self, *, path: Path, audio: torch.Tensor, samplerate: int) -> None:
        x: np.ndarray = audio.detach().cpu().numpy().astype(np.float32)
        if x.ndim != 2:
            raise ValueError(f"audio must be [channels, time]. got shape={x.shape}")
        x = np.transpose(x, (1, 0))
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), x, int(samplerate), subtype="PCM_24")

    #
    async def _mix_many(self, *, input_paths: list[Path], output_path: Path) -> None:
        if len(input_paths) < 2:
            raise ValueError("input_paths must have at least 2 paths")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd: list[str] = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for p in input_paths:
            cmd += ["-i", str(p)]

        cmd += [
            "-filter_complex",
            f"amix=inputs={len(input_paths)}:normalize=0[outa]",
            "-map",
            "[outa]",
            "-c:a",
            "pcm_s24le",
            str(output_path),
        ]

        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg mix_many failed")

    async def _mix_boost(
        self,
        *,
        input_path_first: Path,
        input_path_second: Path,
        output_path: Path,
        gain_db: float,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path_first),
            "-i",
            str(input_path_second),
            "-filter_complex",
            f"[1:a]volume={gain_db}dB[a1];[0:a][a1]amix=inputs=2:normalize=0[outa]",
            "-map",
            "[outa]",
            "-c:a",
            "pcm_s24le",
            str(output_path),
        ]

        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg mix/boost failed")

    async def _dsp_inplace(
        self,
        *,
        path: Path,
        dsp_highpass_hz: float,
        dsp_lowpass_hz: float,
        dsp_force_mono: bool,
        dsp_compress: bool,
    ) -> None:
        if not path.exists():
            raise FileNotFoundError(f"dsp target not found: {path}")

        tmp_path: Path = path.with_suffix(".dsp.tmp.wav")
        if tmp_path.exists():
            tmp_path.unlink()

        filt: str = self._build_dsp_filter(
            dsp_highpass_hz=dsp_highpass_hz,
            dsp_lowpass_hz=dsp_lowpass_hz,
            dsp_force_mono=dsp_force_mono,
            dsp_compress=dsp_compress,
        )

        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-af",
            filt,
            "-c:a",
            "pcm_s24le",
            str(tmp_path),
        ]

        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg dsp failed")

        path.unlink()
        tmp_path.replace(path)

    def _build_dsp_filter(
        self,
        *,
        dsp_highpass_hz: float,
        dsp_lowpass_hz: float,
        dsp_force_mono: bool,
        dsp_compress: bool,
    ) -> str:
        filters: list[str] = []

        hp: float = float(dsp_highpass_hz)
        lp: float = float(dsp_lowpass_hz)

        if hp > 0:
            filters.append(f"highpass=f={hp:.3f}")
        if lp > 0:
            filters.append(f"lowpass=f={lp:.3f}")

        if dsp_compress:
            filters.append("acompressor=threshold=-18dB:ratio=2:attack=5:release=80")

        filters.append("alimiter=limit=0.97")

        if dsp_force_mono:
            filters.append("aformat=channel_layouts=mono")

        return ",".join(filters)

    async def _run_ffmpeg(self, *, cmd: list[str], err_prefix: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err: str = stderr.decode(errors="ignore")
            raise RuntimeError(f"{err_prefix}: {err}")