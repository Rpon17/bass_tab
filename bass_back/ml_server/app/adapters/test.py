import os
import asyncio
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv
import httpx

load_dotenv()

# 환경 변수 로드
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "bass_project")
SUPABASE_STORAGE_BASE_URL = os.getenv("SUPABASE_STORAGE_BASE_URL")

# 클라이언트 초기화
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class SupabaseAudioHandler:
    def __init__(self):
        self.supabase = supabase_client
        self.base_url = SUPABASE_STORAGE_BASE_URL
        self.bucket_name = SUPABASE_BUCKET

    def _get_relative_path(self, full_url: str) -> str:
        if not self.base_url:
            raise ValueError("SUPABASE_STORAGE_BASE_URL이 설정되지 않았습니다.")
        return full_url.replace(self.base_url, "").strip("/")

    async def download_wav_from_url(self, supabase_url: str, local_path: Path) -> bool:
        try:
            relative_path = self._get_relative_path(supabase_url)
            print(f"📥 다운로드 시도: {relative_path}")
            audio_data = self.supabase.storage.from_(self.bucket_name).download(relative_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(audio_data)
            print(f"✅ 로컬 저장 완료: {local_path}")
            return True
        except Exception as e:
            print(f"❌ 다운로드 중 에러 발생: {e}")
            return False

    async def upload_to_supabase_url(self, local_path: Path, target_supabase_url: str) -> bool:
        try:
            if not local_path.exists():
                print(f"❌ 업로드 실패: 로컬 파일이 없습니다. ({local_path})")
                return False
            remote_path = self._get_relative_path(target_supabase_url)
            file_bits = local_path.read_bytes()
            print(f"📤 업로드 시도: {remote_path}")
            self.supabase.storage.from_(self.bucket_name).upload(
                path=remote_path,
                file=file_bits,
                file_options={"content-type": "audio/wav", "upsert": "true"}
            )
            print(f"✅ 업로드 성공: {target_supabase_url}")
            return True
        except Exception as e:
            print(f"❌ 업로드 중 에러 발생: {e}")
            return False
    async def download_test(url, path):
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            if r.status_code == 200:
                path.write_bytes(r.content)
                print("✅ 일반 HTTP로 다운로드 성공! (역시 권한 문제였음)")
            