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
    # 1. redirect_slashes=False: /v1/jobs/ 와 /v1/jobs 를 똑같이 처리해줌
    app: FastAPI = FastAPI(title="Bass Project Main Server", redirect_slashes=False)

    # 2. 허용할 Origin 리스트 (이미지에서 본 진짜 주소 포함)
    origins = [
        "http://localhost:5173",
        "https://bass-project-front-react.onrender.com",
        "https://bass-project-front-react.onrender.com/",
        "https://bass-main-server.onrender.com",
        "https://bass-main-server.onrender.com/",
    ]

    # 3. CORS 미들웨어 설정 (메서드와 헤더를 더 구체적으로 허용)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins, 
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # OPTIONS 명시 필수
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # 4. 라우터 등록 (경로가 겹치지 않게 순서 확인)
    # create_router 안에 있는 /jobs 등이 /v1/jobs 로 등록됨
    app.include_router(create_router, prefix="/v1")
    # song_search_router 안에 있는 경로들이 /v1/songs/... 로 등록됨
    app.include_router(song_search_router, prefix="/v1/songs")

    # 5. 정적 파일 스토리지 설정
    storage_path = os.getenv("STORAGE_ROOT", "/opt/render/project/src/storage")
    if not os.path.exists(storage_path):
        os.makedirs(storage_path, exist_ok=True)
        print(f"[INFO] Storage directory created at: {storage_path}")

    # /files 경로로 정적 파일 서비스
    app.mount("/files", StaticFiles(directory=storage_path), name="storage")

    # 6. 헬스체크 및 루트 경로 (405 방지용 GET)
    @app.get("/")
    async def root():
        return {"status": "ok", "message": "Bass Main Server is running"}

    return app

app: FastAPI = create_app()