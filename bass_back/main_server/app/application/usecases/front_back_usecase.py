import os
from app.application.ports.front_back_port import FrontBackRepositoryPort

class FrontBackUsecase:
    def __init__(self, repository: FrontBackRepositoryPort, base_url: str = "http://localhost:8000"):
        self.repository = repository
        self.base_url = base_url.rstrip("/")

    async def execute(self, query: str) -> list[dict]:
        raw_data = await self.repository.search_songs_with_results(query=query)

        storage_root = os.getenv("STORAGE_ROOT", "C:\\bass_project\\storage")

        for item in raw_data:
            if item.get("result_id"):
                path_keys = [
                    "original_audio_path", "bass_only_path", "bass_removed_path", 
                    "bass_boosted_path", "original_tab_path", "root_tab_path"
                ]
                
                for key in path_keys:
                    path_value = item.get(key)
                    if path_value:
                        relative_path = str(path_value).replace(storage_root, "").replace("\\", "/")
                        
                        if not relative_path.startswith("/"):
                            relative_path = "/" + relative_path
                        
                        item[key] = f"{self.base_url}/files{relative_path}"
        
        return raw_data