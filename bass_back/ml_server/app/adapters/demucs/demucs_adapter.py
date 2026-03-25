from __future__ import annotations

import asyncio
import shutil
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.audio import AudioFile
from demucs.pretrained import get_model
from dotenv import load_dotenv

from app.adapters.ml_supabase_adapter import SupabaseAudioHandler
from app.application.ports.demucs.demucs_port import (
    DemucsPort,
    DemucsSplitSetting,
    DemucsDspParams,
)

load_dotenv()

def _log_step(message: str) -> None:
    print(f"[demucs] {message}")

@dataclass(frozen=True)
class DemucsAdapter(DemucsPort):
    handler: SupabaseAudioHandler = field(default_factory=SupabaseAudioHandler)

    async def split(self, **kwargs) -> Path:
        return await self.split_file(**kwargs)

    async def split_file(
        self,
        *,
        input_wav_path: Path,
        temp_dir: Path,
        asset_id: str,
        output_dir: Path,
        setting: DemucsSplitSetting,
        dsp: DemucsDspParams,
    ) -> Path:
        _log_step(f"🎸 [분석 시작] asset_id: {asset_id}")

        # 1. 로컬 경로 설정 (audio는 MP3 결과물, stem은 작업용 WAV)
        local_root = temp_dir / asset_id
        local_audio_dir = local_root / "audio"
        local_stem_dir = local_root / "stem"
        
        for d in [local_audio_dir, local_stem_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 결과물 파일명 정의 (MP3)
        local_original_mp3 = local_audio_dir / "original.mp3"
        local_bass_only_mp3 = local_audio_dir / "bass_only.mp3"
        local_bass_removed_mp3 = local_audio_dir / "bass_removed.mp3"
        local_bass_boosted_mp3 = local_audio_dir / "bass_boosted.mp3"
        
        # 2. 원본 파일 다운로드 (WAV 분석을 위해 임시 저장)
        target_url = str(input_wav_path)
        if "https:/" in target_url and "https://" not in target_url:
            target_url = target_url.replace("https:/", "https://")

        _log_step(f"📥 다운로드 대상: {target_url}")
        local_temp_raw = local_stem_dir / "input_raw.wav"
        
        # [수정 완료] Handler 인자 이름을 url로 맞춤
        success_download = await self.handler.download_wav_from_url(
            target_url, 
            local_temp_raw,
            max_retries=10 
        )
        if not success_download:
            raise RuntimeError(f"파일 다운로드 실패: {target_url}")

        # 3. [Demucs] 음원 분리 실행
        _log_step(f"⏳ Demucs 분석 중... (Model: {setting.demucs_model})")
        model, samplerate, channels = self._load_model(demucs_model=setting.demucs_model)
        wav_tensor = self._read_audio(input_path=local_temp_raw, samplerate=samplerate, audio_channels=channels)
        sources = self._infer_sources(model=model, wav=wav_tensor)
        
        # 고음질 .wav 중간 결과물들 저장
        stem_paths = self._save_stems(sources=sources, model=model, samplerate=samplerate, demucs_tmp_dir=local_stem_dir)
        
        v_path = stem_paths.get("vocals")
        d_path = stem_paths.get("drums")
        o_path = stem_paths.get("other")
        b_path = stem_paths.get("bass")

        # 4. [오디오 가공] WAV -> MP3 믹싱 및 변환
        _log_step("🛠️ MP3 변환 및 믹싱 공정 진행 중...")
        
        # (1) 원본 MP3 생성
        await self._convert_to_mp3(input_path=local_temp_raw, output_path=local_original_mp3)
        
        # (2) Bass Only 생성
        await self._convert_to_mp3(input_path=b_path, output_path=local_bass_only_mp3)
        
        # (3) Bass Removed (v, d, o 조합)
        await self._make_bass_removed(
            vocals_src=v_path, drums_src=d_path, other_src=o_path, 
            out_path=local_bass_removed_mp3
        )
        
        # (4) Bass Boosted (모든 WAV 조합 + Bass 증폭)
        await self._mix_boost_from_wavs(
            v_path=v_path, d_path=d_path, o_path=o_path, b_path=b_path,
            out_path=local_bass_boosted_mp3, gain_db=setting.boosted_volume_db
        )
        
        # (5) DSP 적용 (필요 시)
        if dsp.enable_dsp:
            await self._dsp_inplace(
                path=local_bass_only_mp3, 
                highpass=dsp.dsp_highpass_hz, 
                lowpass=dsp.dsp_lowpass_hz, 
                mono=dsp.dsp_force_mono, 
                compress=dsp.dsp_compress
            )

        # 5. [결과 업로드]
        # output_dir 주소 보정
        base_output_url = str(output_dir).rstrip("/")
        if not base_output_url.startswith("http"):
            base_output_url = f"{self.handler.base_url}/{base_output_url.lstrip('/')}"
        
        asset_audio_upload_dir = f"{base_output_url}/asset/{asset_id}/audio"
        
        final_upload_map = {
            "original.mp3": local_original_mp3,
            "bass_only.mp3": local_bass_only_mp3,
            "bass_removed.mp3": local_bass_removed_mp3,
            "bass_boosted.mp3": local_bass_boosted_mp3
        }

        _log_step(f"📤 결과 업로드 중... (대상: {asset_audio_upload_dir})")
        for name, local_path in final_upload_map.items():
            target_upload_url = f"{asset_audio_upload_dir}/{name}"
            await self.handler.upload_to_supabase_url(local_path=local_path, target_supabase_url=target_upload_url)
            _log_step(f"   [OK] {name}")

        # 6. 임시 파일 정리
        if setting.cleanup_stems:
            shutil.rmtree(local_stem_dir, ignore_errors=True)

        _log_step(f"✨ 모든 공정 완료 (Asset: {asset_id})")
        return local_bass_only_mp3

    # --- FFmpeg & 유틸리티 메서드 ---

    async def _convert_to_mp3(self, *, input_path: Path, output_path: Path) -> None:
        cmd = ["ffmpeg", "-y", "-i", str(input_path), "-acodec", "libmp3lame", "-aq", "2", str(output_path)]
        await self._run_ffmpeg(cmd=cmd, err_prefix="MP3 conversion failed")

    async def _make_bass_removed(self, *, vocals_src: Path, drums_src: Path, other_src: Path, out_path: Path) -> None:
        cmd = [
            "ffmpeg", "-y", "-i", str(vocals_src), "-i", str(drums_src), "-i", str(other_src),
            "-filter_complex", "amix=inputs=3:normalize=0",
            "-acodec", "libmp3lame", "-aq", "2", str(out_path)
        ]
        await self._run_ffmpeg(cmd=cmd, err_prefix="Bass removal failed")

    async def _mix_boost_from_wavs(self, v_path: Path, d_path: Path, o_path: Path, b_path: Path, out_path: Path, gain_db: float):
        cmd = [
            "ffmpeg", "-y", "-i", str(v_path), "-i", str(d_path), "-i", str(o_path), "-i", str(b_path),
            "-filter_complex", f"[3:a]volume={gain_db}dB[b];[0:a][1:a][2:a][b]amix=inputs=4:normalize=0",
            "-acodec", "libmp3lame", "-aq", "2", str(out_path)
        ]
        await self._run_ffmpeg(cmd=cmd, err_prefix="Boosted mix failed")

    async def _dsp_inplace(self, *, path: Path, highpass: float, lowpass: float, mono: bool, compress: bool) -> None:
        tmp = path.with_suffix(".dsp.tmp.mp3")
        filters = []
        if highpass > 0: filters.append(f"highpass=f={highpass}")
        if lowpass > 0: filters.append(f"lowpass=f={lowpass}")
        if compress: filters.append("acompressor=threshold=-18dB:ratio=2")
        if mono: filters.append("aformat=channel_layouts=mono")
        
        cmd = ["ffmpeg", "-y", "-i", str(path), "-af", ",".join(filters or ["anull"]), "-acodec", "libmp3lame", "-aq", "2", str(tmp)]
        await self._run_ffmpeg(cmd=cmd, err_prefix="DSP failed")
        if tmp.exists():
            if path.exists(): os.remove(path)
            tmp.rename(path)

    # --- Demucs 엔진 메서드 ---

    def _load_model(self, *, demucs_model: str):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = get_model(name=demucs_model)
        model.to(device); model.eval()
        return model, int(getattr(model, "samplerate", 44100)), int(getattr(model, "audio_channels", 2))

    def _read_audio(self, *, input_path: Path, samplerate: int, audio_channels: int):
        wav = AudioFile(str(input_path)).read(samplerate=samplerate, channels=audio_channels)
        return wav.unsqueeze(0) if wav.dim() == 2 else wav

    def _infer_sources(self, *, model: object, wav: torch.Tensor):
        device = next(model.parameters()).device
        with torch.no_grad():
            sources = apply_model(model, wav.to(device), shifts=2, split=True, overlap=0.5, progress=True)
        return sources[0] if sources.dim() == 4 else sources

    def _save_stems(self, *, sources: torch.Tensor, model: object, samplerate: int, demucs_tmp_dir: Path):
        stem_names = list(getattr(model, "sources", []))
        stem_paths = {}
        for i, name in enumerate(stem_names):
            p = demucs_tmp_dir / f"{name}.wav"
            x = sources[i].detach().cpu().numpy().astype(np.float32).T
            sf.write(str(p), x, samplerate, subtype="PCM_24")
            stem_paths[name] = p
        return stem_paths

    async def _run_ffmpeg(self, *, cmd: list[str], err_prefix: str) -> None:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0: raise RuntimeError(f"{err_prefix}: {stderr.decode(errors='ignore')}")