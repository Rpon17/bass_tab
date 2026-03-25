import os
import asyncio
import json
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv
import httpx

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "bass_project")
SUPABASE_STORAGE_BASE_URL = os.getenv("SUPABASE_STORAGE_BASE_URL")

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class SupabaseAudioHandler:
    def __init__(self):
        self.supabase = supabase_client
        self.base_url = SUPABASE_STORAGE_BASE_URL
        self.bucket_name = SUPABASE_BUCKET

    def _get_relative_path(self, full_url: str) -> str:
        full_url = str(full_url)
        target = "results/"
        if target in full_url:
            return target + full_url.split(target)[-1].strip("/")
        if self.base_url and self.base_url in full_url:
            return full_url.replace(self.base_url, "").strip("/")
        return full_url.split("/")[-1]

    async def download_wav_from_url(self, url: str = None, local_path: Path = None, max_retries: int = 10, **kwargs) -> bool:
        # 호출자가 url 대신 target_url로 보내도 받아줍니다.
        actual_url = url or kwargs.get("target_url")
        actual_path = local_path or kwargs.get("local_path")

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(1, max_retries + 1):
                try:
                    print(f"[handler] 📥 다운로드 시도 ({attempt}/{max_retries}): {actual_url}")
                    r = await client.get(str(actual_url))
                    if r.status_code == 200:
                        actual_path.parent.mkdir(parents=True, exist_ok=True)
                        actual_path.write_bytes(r.content)
                        print(f"[handler] ✅ 다운로드 완료: {actual_path}")
                        return True
                    elif r.status_code == 404:
                        print(f"[handler] ⏳ 404 Not Found. 파일 생성 대기 중... (2초 후 재시도)")
                except Exception as e:
                    print(f"[handler] ❌ 통신 에러: {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(2)
            return False

    async def upload_to_supabase_url(self, local_path: Path, target_supabase_url: str) -> bool:
        try:
            if not local_path.exists(): return False
            remote_path = self._get_relative_path(target_supabase_url)
            if local_path.suffix == ".mp3" and remote_path.endswith(".wav"):
                remote_path = remote_path.replace(".wav", ".mp3")
            
            file_bits = local_path.read_bytes()
            extension = local_path.suffix.lower()
            content_type = "audio/mpeg" if extension == ".mp3" else "audio/wav"
            
            self.supabase.storage.from_(self.bucket_name).upload(
                path=remote_path, file=file_bits,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            print(f"[handler] ✅ 업로드 성공: {remote_path}")
            return True
        except Exception as e:
            print(f"[handler] ❌ 업로드 예외: {e}"); return False
            
    async def upload_json_to_supabase(self, payload: list[dict] | dict, target_supabase_url: str) -> bool:
            """
            [필수] JSON 데이터를 메모리에서 직접 Supabase 스토리지로 업로드합니다.
            """
            try:
                import json
                # 1. 데이터를 JSON 문자열로 변환
                json_str = json.dumps(payload, ensure_ascii=False, indent=2)
                file_bits = json_str.encode("utf-8")
                
                # 2. 경로 정제
                remote_path = self._get_relative_path(target_supabase_url)
                
                print(f"[handler] 📤 JSON 업로드 시작: {remote_path}")

                # 3. 업로드 실행
                self.supabase.storage.from_(self.bucket_name).upload(
                    path=remote_path,
                    file=file_bits,
                    file_options={
                        "content-type": "application/json", 
                        "upsert": "true"
                    }
                )
                print(f"[handler] ✅ JSON 업로드 완료")
                return True
                
            except Exception as e:
                print(f"[handler] ❌ JSON 업로드 에러: {e}")
                return False