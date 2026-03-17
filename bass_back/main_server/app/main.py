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
    # redirect_slashes=False: 주소 끝에 / 유무로 에러나는 걸 방지해줘
    app: FastAPI = FastAPI(title="Bass Project Main Server", redirect_slashes=False)

    origins = [
        "http://localhost:5173",
        "https://bass-project-front-react.onrender.com",
        "https://bass-project-front-react.onrender.com/",
        # 👇 캡처 이미지에서 확인한 진짜 서버 주소를 추가했어!
        "https://bass-main-server.onrender.com",
        "https://bass-main-server.onrender.com/",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins, 
        allow_credentials=True,
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

    # 렌더 헬스체크용 루트 경로 (있으면 배포가 더 안정적이야)
    @app.get("/")
    async def root():
        return {"message": "Server is running"}

    return app

app: FastAPI = create_app()