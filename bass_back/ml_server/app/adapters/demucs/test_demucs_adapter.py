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
    # 핸들러 초기화 (Factory 사용)
    handler: SupabaseAudioHandler = field(default_factory=SupabaseAudioHandler)

    async def split(self, **kwargs) -> Path:
        """Port 인터페이스의 split 호출을 실제 구현부로 연결"""
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
        _log_step(f"[분석 시작] asset_id: {asset_id} (Engine: {setting.demucs_model})")

        # 1. 로컬 경로 및 디렉토리 설정
        _log_step(f"로컬경로 생성")
        local_root = temp_dir / asset_id
        local_audio_dir = local_root / "audio"  
        local_stem_dir = local_root / "stem"     
        
        # temp_dir=storage_root , STORAGE_ROOT=./storage
        
        # C:\bass_project\bass_back\ml_server\app\adapters\demucs\demucs_adapter.py
        # C:\bass_project\bass_back\ml_server\app\adapters\demucs\asset_id\stem 
        # local_audio_dir ./storage/asset_id/audio
        # local_stem_dir  ./storage/asset_id/stem
        for d in [local_audio_dir, local_stem_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 저장할 목적지 만들기
        local_original = local_audio_dir / "original.wav"
        local_bass_only = local_audio_dir / "bass_only.wav"
        local_bass_removed = local_audio_dir / "bass_removed.wav"
        local_bass_boosted = local_audio_dir / "bass_boosted.wav"

        # 2. 원본 파일 다운로드 (URL 정규화 포함)
        _log_step("원본파일 다운로드")
        target_url = str(input_wav_path)
        if "https:/" in target_url and "https://" not in target_url:
            target_url = target_url.replace("https:/", "https://")

        success_download = await self.handler.download_wav_from_url(
            target_url, 
            local_original,
            max_retries=10 
        )
        if not success_download:
            raise RuntimeError(f"파일 다운로드 실패: {target_url}")

        # 3. [Demucs] 음원 분리 실행
        _log_step("Demucs 음원 분리 중... (이 과정은 시간이 소요됩니다)")
        model, samplerate, channels = self._load_model(demucs_model=setting.demucs_model)
        wav_tensor = self._read_audio(input_path=local_original, samplerate=samplerate, audio_channels=channels)
        sources = self._infer_sources(model=model, wav=wav_tensor)
        
        # Stem 파일들 저장
        stem_paths = self._save_stems(sources=sources, model=model, samplerate=samplerate, demucs_tmp_dir=local_stem_dir)
        
        v_path = stem_paths.get("vocals")
        d_path = stem_paths.get("drums")
        o_path = stem_paths.get("other")
        b_path = stem_paths.get("bass")

        # 2. 만약 파일이 없을 때 에러를 내고 싶다면 (권장)
        if not v_path:
            raise RuntimeError("보컬 파일을 찾을 수 없습니다!")

        # 4. [오디오 가공] 추출, 제거, 강조본 생성
        _log_step("오디오 믹싱 및 DSP 처리 중...")
        
        # (1) Bass Only 복사
        self._copy_file(input_path=b_path, output_path=local_bass_only, overwrite=setting.overwrite_outputs)
        
        # (2) Bass Removed 생성
        await self._make_bass_removed(
            vocals_src=v_path, drums_src=d_path, other_src=o_path, 
            out_path=local_bass_removed, overwrite=setting.overwrite_outputs
        )
        
        # (3) Bass Boosted 생성
        await self._make_bass_boosted(
            bass_removed_path=local_bass_removed, bass_only_path=local_bass_only, 
            out_path=local_bass_boosted, gain_db=setting.boosted_volume_db, overwrite=setting.overwrite_outputs
        )

        # (4) DSP 적용
        if dsp.enable_dsp:
            await self._dsp_inplace(
                path=local_bass_only, 
                highpass=dsp.dsp_highpass_hz, 
                lowpass=dsp.dsp_lowpass_hz, 
                mono=dsp.dsp_force_mono, 
                compress=dsp.dsp_compress
            )

        # 5. [업로드] 생성된 모든 파일 Supabase로 전송
        # output_dir이 URL인지 확인 후 정규화
        base_output_url = str(output_dir).rstrip("/")
        if not base_output_url.startswith("http"):
            base_output_url = f"{self.handler.base_url}/{base_output_url.lstrip('/')}"
        
        asset_audio_upload_dir = f"{base_output_url}/asset/{asset_id}/audio"
        final_files = {
            "original.wav": local_original,
            "bass_only.wav": local_bass_only,
            "bass_removed.wav": local_bass_removed,
            "bass_boosted.wav": local_bass_boosted
        }

        _log_step(f"📤 결과 업로드 중... ({asset_audio_upload_dir})")
        for name, local_path in final_files.items():
            target_upload_url = f"{asset_audio_upload_dir}/{name}"
            await self.handler.upload_to_supabase_url(local_path=local_path, target_supabase_url=target_upload_url)

        # 6. 임시 파일 정리
        if setting.cleanup_stems:
            shutil.rmtree(local_stem_dir, ignore_errors=True)

        _log_step(f"✨ 모든 공정 완료! asset_id: {asset_id}")
        return local_bass_only

    # --- 헬퍼 메서드 (안전한 호출을 위해 가급적 키워드 인자 사용) ---

    def _copy_file(self, *, input_path: Path, output_path: Path, overwrite: bool) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if input_path.resolve() == output_path.resolve(): return
        if output_path.exists() and not overwrite: return
        shutil.copyfile(str(input_path), str(output_path))

    def _load_model(self, *, demucs_model: str) -> tuple[object, int, int]:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _log_step(f"모델 로딩 중 ({demucs_model}) - Device: {device}")
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
            sources = apply_model(model, wav.to(device), shifts=2, split=True, overlap=0.5, progress=True)
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

    def _require_stem(self, stem_paths: dict[str, Path], name: str) -> Path:
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

    # bass_removed 만듬
    async def _mix_many(self, *, input_paths: list[Path], output_path: Path) -> None:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for p in input_paths: cmd += ["-i", str(p)]
        cmd += ["-filter_complex", f"amix=inputs={len(input_paths)}:normalize=0[outa]", "-map", "[outa]", "-c:a", "pcm_s24le", str(output_path)]
        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg mix failed")

    # ㅇbass_boost만듬
    async def _mix_boost(self, *, input_path_first: Path, input_path_second: Path, output_path: Path, gain_db: float) -> None:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_path_first), "-i", str(input_path_second),
               "-filter_complex", f"[1:a]volume={gain_db}dB[a1];[0:a][a1]amix=inputs=2:normalize=0[outa]",
               "-map", "[outa]", "-c:a", "pcm_s24le", str(output_path)]
        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg boost failed")

    async def _dsp_inplace(self, *, path: Path, highpass: float, lowpass: float, mono: bool, compress: bool) -> None:
        tmp = path.with_suffix(".dsp.tmp.wav")
        filters = []
        if highpass > 0: filters.append(f"highpass=f={highpass}")
        if lowpass > 0: filters.append(f"lowpass=f={lowpass}")
        if compress: filters.append("acompressor=threshold=-18dB:ratio=2")
        filters.append("alimiter=limit=0.97")
        if mono: filters.append("aformat=channel_layouts=mono")
        
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-af", ",".join(filters), "-c:a", "pcm_s24le", str(tmp)]
        await self._run_ffmpeg(cmd=cmd, err_prefix="ffmpeg dsp failed")
        
        # 파일 교체 시 잠시 대기 (Windows 액세스 충돌 방지)
        await asyncio.sleep(0.2)
        if tmp.exists():
            if path.exists(): os.remove(path)
            tmp.rename(path)

    # other vocal drum만 있으면 됨
    async def _make_bass_removed(self, *, vocals_src: Path, drums_src: Path, other_src: Path, out_path: Path, overwrite: bool) -> None:
        if out_path.exists() and not overwrite: return
        await self._mix_many(input_paths=[vocals_src, drums_src, other_src], output_path=out_path)

    # remove only output_path 만 필요함
    async def _make_bass_boosted(self, *, bass_removed_path: Path, bass_only_path: Path, out_path: Path, gain_db: float, overwrite: bool) -> None:
        if out_path.exists() and not overwrite: return
        await self._mix_boost(input_path_first=bass_removed_path, input_path_second=bass_only_path, output_path=out_path, gain_db=gain_db)