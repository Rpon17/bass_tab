import os
from app.application.ports.front_back_port import FrontBackRepositoryPort

class FrontBackUsecase:
    def __init__(self, repository: FrontBackRepositoryPort, base_url: str = None):
        self.repository = repository
        # base_url이 없으면 환경변수에서 가져오거나 기본값 설정
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

    async def execute(self, query: str) -> list[dict]:
        raw_data = await self.repository.search_songs_with_results(query=query)

        # 💡 클라우드 서버(Linux) 환경을 고려한 기본값 설정
        storage_root = os.getenv("STORAGE_ROOT", "/app/storage") 

        path_keys = [
            "original_audio_path", "bass_only_path", "bass_removed_path", 
            "bass_boosted_path", "original_tab_path", "root_tab_path"
        ]

        for item in raw_data:
            for key in path_keys:
                path_value = item.get(key)
                if path_value and str(path_value).strip():
                    # 💡 더 안전한 경로 치환 방식
                    # 1. 윈도우 스타일의 역슬래시(\)를 슬래시(/)로 통합
                    # 2. storage_root 부분도 슬래시로 바꿔서 제거
                    clean_path = str(path_value).replace("\\", "/")
                    clean_root = storage_root.replace("\\", "/")
                    
                    relative_path = clean_path.replace(clean_root, "").lstrip("/")
                    
                    # 최종 URL 조립
                    item[key] = f"{self.base_url}/files/{relative_path}"
        
        return raw_data