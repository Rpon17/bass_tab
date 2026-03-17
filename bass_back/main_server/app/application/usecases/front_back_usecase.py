from app.application.ports.front_back_port import FrontBackRepositoryPort

class FrontBackUsecase:
    def __init__(self, repository: FrontBackRepositoryPort, base_url: str = "http://localhost:8000"):
        self.repository = repository
        self.base_url = base_url

    async def execute(self, query: str) -> list[dict]:
        # 1. DB에서 지금 보여주신 C:\... 가 포함된 데이터를 가져옵니다.
        raw_data = await self.repository.search_songs_with_results(query=query)
        
        # DB에 저장된 로컬 경로의 앞부분
        storage_root = "C:\\bass_project\\storage"

        for item in raw_data:
            if item.get("result_id"):
                path_keys = [
                    "original_audio_path", "bass_only_path", "bass_removed_path", 
                    "bass_boosted_path", "original_tab_path", "root_tab_path"
                ]
                
                for key in path_keys:
                    if item.get(key):
                    
                        relative_path = str(item[key]).replace(storage_root, "").replace("\\", "/")
                        item[key] = f"{self.base_url}/files{relative_path}"
        
        return raw_data