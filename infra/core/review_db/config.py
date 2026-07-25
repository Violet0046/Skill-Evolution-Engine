"""
review_db.config — MySQL 连接配置

加载优先级:
    1. 进程环境变量 (REVIEW_DB_*)
    2. 项目根 .env 文件 (KEY=VALUE 格式, 每行一条, # 开头为注释)

ReviewDbConfig.from_env() 在 REVIEW_DB_HOST 未设置时返回 None,
借此让 review_db 的所有钩子在配置缺失时静默 no-op, 不阻塞流水线.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ReviewDbConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    # worker 配置
    queue_maxsize: int = 10_000
    worker_join_timeout: float = 10.0

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> Optional["ReviewDbConfig"]:
        """
        若 REVIEW_DB_HOST (或公司统一别名 DQ_DB_HOST) 缺失则返回 None.
        不抛异常 — 该函数只做配置加载, 不应阻塞调用方.

        兼容两种环境变量命名 (优先级从高到低):
          1. REVIEW_DB_* (本项目约定的命名)
          2. DQ_DB_*     (公司基础设施的命名约定)
        """
        # 1. 先用 os.environ (外部 export 进来的优先级最高)
        env = dict(os.environ)

        # 2. 再扫 .env 文件作为补充, 不覆盖已有 env 项
        if env_path is None:
            # 默认尝试: 项目根/.env
            env_path = _project_root() / ".env"
        parsed_dotenv = _load_dotenv(env_path)
        for k, v in parsed_dotenv.items():
            env.setdefault(k, v)

        # 公司 DQ_DB_* 别名补集 (仅当 REVIEW_DB_* 未设时填充, 不覆盖已有值)
        aliases = {
            "REVIEW_DB_HOST":     "DQ_DB_HOST",
            "REVIEW_DB_PORT":     "DQ_DB_PORT",
            "REVIEW_DB_USER":     "DQ_DB_USER",
            "REVIEW_DB_PASSWORD": "DQ_DB_PWD",
            "REVIEW_DB_DATABASE": "DQ_DB_NAME",
        }
        for review_key, dq_key in aliases.items():
            if not env.get(review_key):
                v = env.get(dq_key)
                if v is not None:
                    env[review_key] = v

        host = env.get("REVIEW_DB_HOST")
        if not host:
            return None

        return cls(
            host=host,
            port=int(env.get("REVIEW_DB_PORT", "3306")),
            user=env.get("REVIEW_DB_USER", "root"),
            password=env.get("REVIEW_DB_PASSWORD", ""),
            database=env.get("REVIEW_DB_DATABASE", "knowledge_engineering"),
            queue_maxsize=int(env.get("REVIEW_DB_QUEUE_MAXSIZE", "10000")),
            worker_join_timeout=float(env.get("REVIEW_DB_WORKER_TIMEOUT", "10.0")),
        )


def _project_root() -> Path:
    """infra/core/review_db/ -> 工程根 (3 层 parent)."""
    return Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path) -> dict[str, str]:
    """
    极简 .env 解析器:
    - 每行一条 KEY=VALUE
    - 行首 # 或 // 视为注释
    - 空行跳过
    - 不支持 shell 展开 ($VAR), 不支持引号
    - 文件不存在返回空 dict (不报错)
    """
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return out
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        if "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip()
        # 不去引号 (简化: 用户应在 .env 里写不带引号的值)
        if k:
            out[k] = v
    return out


if __name__ == "__main__":  # 调试入口: python -m core.review_db.config
    cfg = ReviewDbConfig.from_env()
    if cfg is None:
        print("REVIEW_DB_HOST 未配置; review_db 将 no-op", file=sys.stderr)
    else:
        print(cfg)
