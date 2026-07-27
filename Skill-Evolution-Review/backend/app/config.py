"""
backend/app/config.py — 应用配置 (从 .env 读)

.env 路径:
  Settings 默认从 cwd 寻找 .env — 启动 uvicorn 时应该在 backend/ 目录运行,
  这样它能找到 backend/.env. 我们也加一个绝对路径兜底以便 .py 单独 import 时可用.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/.env 绝对路径, 让"从任意目录执行 import app" 都能找到 .env
_DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """应用配置. 字段名对应 env vars:

    REVIEW_DB_HOST     -> review_db_host
    REVIEW_DB_PORT     -> review_db_port (默认 3306)
    REVIEW_DB_USER     -> review_db_user
    REVIEW_DB_PASSWORD -> review_db_password
    REVIEW_DB_DATABASE -> review_db_database
    """
    review_db_host: str
    review_db_port: int = 3306
    review_db_user: str
    review_db_password: str
    review_db_database: str

    model_config = SettingsConfigDict(
        env_file=str(_DEFAULT_ENV_FILE),
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sqlalchemy_url(self) -> str:
        """拼装 SQLAlchemy URL.

        返回示例:
          mysql+pymysql://user:pwd@host:3306/db?charset=utf8mb4

        不在 URL 中编码密码到日志, 但 pydantic 日志可能泄露 fields, 注意.
        """
        return (
            f"mysql+pymysql://{self.review_db_user}:{self.review_db_password}"
            f"@{self.review_db_host}:{self.review_db_port}/{self.review_db_database}"
            f"?charset=utf8mb4"
        )

    @property
    def sqlalchemy_url_safe(self) -> str:
        """无密码 URL, 用于 debug / log."""
        return (
            f"mysql+pymysql://{self.review_db_user}:***"
            f"@{self.review_db_host}:{self.review_db_port}/{self.review_db_database}"
            f"?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    """全局单例: 第一次调用时实例化, 之后从 cache 取."""
    return Settings()
