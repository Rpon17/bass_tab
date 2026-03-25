from __future__ import annotations

import asyncio
import shutil
import uuid
import os
from dataclasses import dataclass,field
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.audio import AudioFile
from demucs.pretrained import get_model
from supabase import create_client, Client
from dotenv import load_dotenv

from app.adapters.ml_supabase_adapter import SupabaseAudioHandler
from app.application.ports.demucs.demucs_port import (
    DemucsPort,
    DemucsSplitSetting,
    DemucsDspParams,
)

load_dotenv()

def _log_step(message: str) -> None:
    print(f"[fake-ml-server] {message}")

@dataclass(frozen=True)
class FakeDemucsAdapter(DemucsPort):
    fake_delay_seconds: float = 1.0  # 분석 시간을 조금 더 현실적으로 1초로 설정
    
    # 핸들러 초기화
    handler: SupabaseAudioHandler = field(default_factory=SupabaseAudioHandler)

    async def split(self, **kwargs) -> Path:
        return await self.split_file(**kwargs)

    async def split_file(
        self,
        *,
        input_wav_path: Path,
        temp_dir:Path,
        asset_id: str,
        output_dir: Path,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> Path:
        _log_step(f"🎸 [분석 시작] asset_id: {asset_id}")

        # 1. 로컬 경로 설정
        local_root = temp_dir / asset_id
        local_audio_dir = local_root / "audio"
        local_audio_dir.mkdir(parents=True, exist_ok=True)
        local_original = local_audio_dir / "original.wav"
        local_bass_only_path = local_audio_dir / "bass_only.wav"
        
        # 2. 다운로드 대상 URL
        target_url = str(input_wav_path)
        _log_step(f"📥 다운로드 대상: {target_url}")

        # 3. 핸들러를 사용하여 다운로드 main에서 변환하는데 꽤 걸리므로 10초정도는 대기함
        success_download = await self.handler.download_wav_from_url(
            target_url, 
            local_original,
            max_retries=10 
        )

        if not success_download:
            _log_step(f"❌ 원본 파일 확보 실패 (최종 실패)")
            raise RuntimeError(f"파일을 가져올 수 없습니다: {target_url}")

        # 4. 가짜 분석 딜레이
        _log_step(f"⏳ 분석 중... ({self.fake_delay_seconds}s)")
        await asyncio.sleep(self.fake_delay_seconds)

        # 5. 결과 업로드
        file_names = ["original.wav", "bass_only.wav", "bass_removed.wav", "bass_boosted.wav"]
        
        import shutil
        for name in file_names:
            target_local_path = local_audio_dir / name
            if not target_local_path.exists():
                shutil.copy2(local_original, target_local_path)
                
        # output_dir 보정
        base_output_url = str(output_dir).rstrip("/")
        if not base_output_url.startswith("http"):
             # handler의 base_url(bass_project)을 사용하여 주소 완성
            base_output_url = f"{self.handler.base_url}/{base_output_url.lstrip('/')}"
        
        asset_upload_dir = f"{base_output_url}/asset/{asset_id}/audio"
        
        _log_step(f"📤 결과 업로드 중... (대상: {base_output_url}/audio/)")

        for name in file_names:
            target_upload_url = f"{asset_upload_dir}/{name}"
            await self.handler.upload_to_supabase_url(local_original, target_upload_url)
            _log_step(f"   [OK] {name}")

        _log_step(f"✨ 모든 공정 완료")
        
        return local_bass_only_path

    # --- 헬퍼 메서드 (기존 로직 유지) ---

    def _copy_file(self, *, input_path: Path, output_path: Path, overwrite: bool) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if input_path.resolve() == output_path.resolve(): return
        if output_path.exists() and not overwrite: return
        shutil.copyfile(str(input_path), str(output_path))

    def _load_model(self, *, demucs_model: str) -> tuple[object, int, int]:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = get_model(name=demucs_model)
        model.to(device)
        model.eval()
        samplerate = int(getattr(model, "samplerate", 44100))
        audio_channels = int(getattr(model, "audio_channels", 2))
        return model, samplerate, audio_channels

    def _read_audio(self, *, input_path: Path, samplerate: int, audio_channels: int) -> torch.Tensor:
        wav = AudioFile(str(input_path)).read(samplerate=samplerate, channels=audio_channels)
        if wav.dim() == 2: wav = wav.unsqueeze(0)
        return wav

    def _infer_sources(self, *, model: object, wav: torch.Tensor) -> torch.Tensor:
        device = next(model.parameters()).device
        with torch.no_grad():
            sources = apply_model(model, wav.to(device), shifts=2, split=True, overlap=0.5, progress=False)
        if sources.dim() == 4: sources = sources[0]
        return sources

    def _save_stems(self, *, sources: torch.Tensor, model: object, samplerate: int, demucs_tmp_dir: Path) -> dict[str, Path]:
        stem_names = list(getattr(model, "sources", []))
        stem_paths = {}
        for i, name in enumerate(stem_names):
            stem_path = demucs_tmp_dir / f"{name}.wav"
            self._write_wav(path=stem_path, audio=sources[i], samplerate=samplerate)
            stem_paths[name] = stem_path
        return stem_paths

    def _require_stem(self, *, stem_paths: dict[str, Path], name: str) -> Path:
        p = stem_paths.get(name)
        if not p: raise RuntimeError(f"Stem {name} missing")
        return p

    def _write_wav(self, *, path: Path, audio: torch.Tensor, samplerate: int) -> None:
        x = audio.detach().cpu().numpy().astype(np.float32)
        x = np.transpose(x, (1, 0))
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), x, samplerate, subtype="PCM_24")

    async def _run_ffmpeg(self, *, cmd: list[str], err_prefix: str) -> None:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"{err_prefix}: {stderr.decode(errors='ignore')}")

    async def _mix_many(self, *, input_paths: list[Path], output_path: Path) -> None:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for p in input_paths: cmd += ["-i", str(p)]
        cmd += ["-filter_complex", f"amix=inputs={len(input_paths)}:normalize=0[outa]", "-map", "[outa]", "-c:a", "pcm_s24le", str(output_path)]
        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg mix failed")

    async def _mix_boost(self, *, input_path_first: Path, input_path_second: Path, output_path: Path, gain_db: float) -> None:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_path_first), "-i", str(input_path_second),
               "-filter_complex", f"[1:a]volume={gain_db}dB[a1];[0:a][a1]amix=inputs=2:normalize=0[outa]",
               "-map", "[outa]", "-c:a", "pcm_s24le", str(output_path)]
        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg boost failed")

    async def _dsp_inplace(self, path: Path, highpass: float, lowpass: float, mono: bool, compress: bool) -> None:
        tmp = path.with_suffix(".dsp.tmp.wav")
        filters = []
        if highpass > 0: filters.append(f"highpass=f={highpass}")
        if lowpass > 0: filters.append(f"lowpass=f={lowpass}")
        if compress: filters.append("acompressor=threshold=-18dB:ratio=2")
        filters.append("alimiter=limit=0.97")
        if mono: filters.append("aformat=channel_layouts=mono")
        
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-af", ",".join(filters), "-c:a", "pcm_s24le", str(tmp)]
        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg dsp failed")
        tmp.replace(path)

    async def _make_bass_removed(self, *, vocals_src: Path, drums_src: Path, other_src: Path, out_path: Path, overwrite: bool) -> None:
        if out_path.exists() and not overwrite: return
        await self._mix_many(input_paths=[vocals_src, drums_src, other_src], output_path=out_path)

    async def _make_bass_boosted(self, *, bass_removed_path: Path, bass_only_path: Path, out_path: Path, gain_db: float, overwrite: bool) -> None:
        if out_path.exists() and not overwrite: return
        await self._mix_boost(input_path_first=bass_removed_path, input_path_second=bass_only_path, output_path=out_path, gain_db=gain_db)