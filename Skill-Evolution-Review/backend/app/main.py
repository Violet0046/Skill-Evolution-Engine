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
        description="评审系统后端: 4 个核心 API .",
    )

    # CORS — 同源部署 (nginx 反代) 时不需 CORS; 但保留以下 origin 给:
    # 1) 本地 dev 调试 (vite dev 5173, 后端 8000)
    # 2) 同事可能从 host 直接访问 (没有 nginx 反代场景)
    # 3) host 内网 IP 让 IP 直接访问也行
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            # dev: 直接 dev server
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            # 部署后: 同源访问不需要 CORS, 但多 origin 不会报错
            # 公司同事可能在 host IP 直连 (无 nginx 反代)
            "http://10.90.213.38:5180",       # 公司这台机器 + 部署端口 (按你 DEPLOY.md 调整)
            "http://10.90.213.38",             # 如果改用 80 端口
            "http://localhost:5180",
            "http://127.0.0.1:5180",
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
