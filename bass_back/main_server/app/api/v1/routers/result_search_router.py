from fastapi import APIRouter, Depends, HTTPException
from app.api.v1.deps import get_get_results_by_song_uc # 의존성 주입 함수
from app.application.usecases.songs.get_results_by_song_usecase import GetResultsBySongUseCase

router = APIRouter()

@router.get("/{song_id}")
async def get_results_by_song(
    song_id: str,
    usecase: GetResultsBySongUseCase = Depends(get_get_results_by_song_uc)
):
    try:
        results = await usecase.execute(song_id=song_id)
        if not results:
            raise HTTPException(status_code=404, detail="해당 곡의 결과물을 찾을 수 없습니다.")
        return results
    except Exception as e:
        # 에러 발생 시 로그 출력 및 예외 처리
        print(f"[API_ERROR] {e}")
        raise HTTPException(status_code=500, detail="서버 처리 중 오류가 발생했습니다.")