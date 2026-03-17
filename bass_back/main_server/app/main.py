from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.routers.create_router import router as create_router
from app.api.v1.routers.front_back_router import router as song_search_router

def create_app() -> FastAPI:
    app: FastAPI = FastAPI(title="Bass Project Main Server")

    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(create_router, prefix="/v1")
    app.include_router(song_search_router, prefix="/v1/songs")

    storage_path = os.getenv("STORAGE_ROOT", "C:/bass_project/storage")
    if os.path.exists(storage_path):
        app.mount("/files", StaticFiles(directory=storage_path), name="storage")

    return app

app: FastAPI = create_app()