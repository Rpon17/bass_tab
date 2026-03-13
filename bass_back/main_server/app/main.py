from __future__ import annotations

from fastapi import FastAPI

# 네 라우터 경로에 맞게 import 경로를 조정해줘.
# 예시: app/api/v1/routers/jobs.py, app/api/v1/routers/ml_connect.py 등이 있다고 가정.
from app.api.v1.routers import jobs  # type: ignore
# 만약 ml_connect를 쓰고 있으면 아래도 include 가능(지금은 1번 구조라 필수 아님)
# from app.api.v1.routers import ml_connect  # type: ignore


def create_app() -> FastAPI:
    app: FastAPI = FastAPI(title="main_server")

    # v1 라우터 등록
    app.include_router(jobs.router, prefix="/v1")

    # (선택) 브리지 라우터 등록 - 1번(직통)에서는 없어도 됨
    # app.include_router(ml_connect.router, prefix="/v1")

    return app


app: FastAPI = create_app()
