from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.routers.process_router import router as process_router
from app.api.v1.routers.status import router as status_router

app: FastAPI = FastAPI(title="bass-ml-server")

# ML process API
app.include_router(process_router)

# ML status API
app.include_router(status_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ml_server running"}