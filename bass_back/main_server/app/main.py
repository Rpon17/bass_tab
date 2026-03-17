from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from app.api.v1.routers.create_router import router as create_router
from app.api.v1.routers.front_back_router import router as song_search_router

def create_app() -> FastAPI:
    # redirect_slashes=False로 설정해서 주소 끝에 /가 붙어도 리다이렉트 없이 처리
    app: FastAPI = FastAPI(title="Bass Project Main Server", redirect_slashes=False)

    # 🛑 모든 접속을 허용하는 설정 (테스트용)
    # allow_credentials=True와 origins=["*"]는 같이 쓸 수 없어서 
    # 대신 allow_origin_regex를 쓰거나 아래처럼 설정해!
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], 
        allow_credentials=False, # ["*"] 일 때는 False로 해야 에러가 안 나!
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(create_router, prefix="/v1")
    app.include_router(song_search_router, prefix="/v1/songs")

    storage_path = os.getenv("STORAGE_ROOT", "/opt/render/project/src/storage")
    
    if not os.path.exists(storage_path):
        os.makedirs(storage_path, exist_ok=True)
        print(f"[INFO] Storage directory created at: {storage_path}")

    app.mount("/files", StaticFiles(directory=storage_path), name="storage")

    # 서버 상태 확인용 루트 경로
    @app.get("/")
    async def root():
        return {"status": "ok", "message": "Server is running"}

    return app

app: FastAPI = create_app()