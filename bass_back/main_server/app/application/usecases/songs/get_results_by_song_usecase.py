from pathlib import Path
from dataclasses import dataclass
import os

from app.application.ports.result_repostiroty_port import ResultRepositoryPort
from app.application.services.path_maker import audio_path, tab_path # 만들어두신 함수 import


@dataclass(frozen=True)
class GetResultsBySongUseCase:
    result_repository: ResultRepositoryPort

    async def execute(self, *, song_id: str):
        # 1. 환경변수에서 저장소 루트 가져오기
        storage_root = Path(os.getenv("STORAGE_ROOT", "C:/bass_project/storage"))
        results_dir = storage_root / "results"
        
        results = await self.result_repository.get_all_by_song_id(song_id=song_id)
        
        processed_results = []
        for r in results:
            # result_id 경로 설정
            result_dir = results_dir / r.result_id
            
            # asset_id가 DB에 없다면 탐색 (있다면 r.asset_id 그대로 사용)
            assets_dir = result_dir / "assets"
            # 첫 번째 폴더를 asset_id로 간주
            aid = [d.name for d in assets_dir.iterdir() if d.is_dir()][0] 
            
            # 2. 웹 URL 변환 함수 (StaticFiles 마운트 경로에 맞게)
            def to_web_url(full_path: str):
                return full_path.replace(str(storage_root), "/files").replace("\\", "/")

            processed_results.append({
                "result_id": r.result_id,
                "audio": {
                    "original": to_web_url(audio_path(result_dir, aid, "original.wav")),
                    "bass_only": to_web_url(audio_path(result_dir, aid, "bass_only.wav")),
                    "bass_removed": to_web_url(audio_path(result_dir, aid, "bass_removed.wav")),
                    "bass_boosted": to_web_url(audio_path(result_dir, aid, "bass_boosted.wav"))
                
                },
                "tab": {
                    "original": to_web_url(tab_path(result_dir, aid, "original_tab.json")),
                    "root": to_web_url(tab_path(result_dir, aid, "root _tab.json"))
                }
            })
        return processed_results