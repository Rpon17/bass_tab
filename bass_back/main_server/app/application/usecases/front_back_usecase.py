import os
from app.application.ports.front_back_port import FrontBackRepositoryPort

class FrontBackUsecase:
    def __init__(self, repository: FrontBackRepositoryPort, base_url: str = None):
        self.repository = repository
        
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

    async def execute(self, query: str) -> list[dict]:
            raw_data = await self.repository.search_songs_with_results(query=query)

            storage_root = os.getenv("STORAGE_ROOT", "/app/storage") 

            path_keys = [
                "original_audio_path", "bass_only_path", "bass_removed_path", 
                "bass_boosted_path", "original_tab_path", "root_tab_path"
            ]

            for item in raw_data:
                for key in path_keys:
                    path_value = item.get(key)
                    if path_value and str(path_value).strip():
                        clean_path = str(path_value).replace("\\", "/")
                        
                        
                        if clean_path.startswith("http"):
                            item[key] = clean_path
                            continue # 다음 키로 넘어감

                    
                        clean_root = storage_root.replace("\\", "/")
                        relative_path = clean_path.replace(clean_root, "").lstrip("/")
                        
                        item[key] = f"{self.base_url}/files/{relative_path}"
            
            return raw_data