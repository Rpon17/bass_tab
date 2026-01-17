# ml_server/app/main.py
from fastapi import FastAPI
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.process import router as process_router

# 이 이 app 객체가서버 그 자체이자 모든 요청의 진입점이 됨
app = FastAPI(title="ML Server", version="1.0.0")

# include_router의 일 “process_router 안에 정의된 모든 엔드포인트를을 FastAPI 앱에 등록해라”
app.include_router(health_router)
app.include_router(process_router)
