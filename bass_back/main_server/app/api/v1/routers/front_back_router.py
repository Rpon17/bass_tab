from fastapi import APIRouter, Depends, Query
from app.api.v1.deps import get_front_back_uc
from app.application.usecases.front_back_usecase import FrontBackUsecase

router = APIRouter()

@router.get("/search") 
async def search_all_data(
    q: str = Query(..., min_length=1, description="노래 제목이나 아티스트 검색어"),
    limit: int = Query(10, ge=1, le=20),
    usecase: FrontBackUsecase = Depends(get_front_back_uc)
):
    results = await usecase.execute(query=q)
    return results