from fastapi import APIRouter
from app.api.v1.routers import jobs
from bass_back.main_server.app.api.v1.routers import song_search_router


api_router = APIRouter()

api_router.include_router(jobs.router)
api_router.include_router(song_search_router.router)