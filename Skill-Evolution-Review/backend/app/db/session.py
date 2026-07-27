"""
backend/app/db/session.py — SQLAlchemy engine + session 工厂

开干 1 暂不实际连 DB. 此文件定义 engine 工厂供开干 2 引用.
"""
from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


_settings = get_settings()

# pool_size=5: FastAPI 单进程并发场景够用, 同时避免对 MySQL 太多连接.
# pool_pre_ping=True: 防止 MySQL wait_timeout 杀掉长连接后拿到的连接失效.
engine: Engine = create_engine(
    _settings.sqlalchemy_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,   # 30 分钟强制回收
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Iterator[Session]:
    """FastAPI Depends 用的 session 上下文. 用法:

        @router.get(...)
        def handler(db: Session = Depends(get_db)):
            ...

    自动 close, 异常时也 close.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
