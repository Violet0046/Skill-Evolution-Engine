"""
backend/app/main.py — FastAPI 应用入口
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.changes import router as changes_router
from app.api.decisions import router as decisions_router
from app.api.evidences import router as evidences_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Review System API",
        version="0.1.0",
        description="评审系统后端: 4 个核心 API (开干 1 阶段, 路由 stub).",
    )

    # CORS — 开干 1 允许前端 localhost:5173
    # 后续 docker-compose 时改为前端容器名
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 健康检查
    @app.get("/healthz", tags=["health"])
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    # 路由挂载
    app.include_router(changes_router)
    app.include_router(evidences_router)
    app.include_router(decisions_router)

    return app


app = create_app()
