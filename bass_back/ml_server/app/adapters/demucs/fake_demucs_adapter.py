from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
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