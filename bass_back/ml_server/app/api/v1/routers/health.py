# ml_server/app/api/v1/routers/health.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health():
    return {"status": "ok"}
