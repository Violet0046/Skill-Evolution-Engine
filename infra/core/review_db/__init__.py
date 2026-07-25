"""
review_db — SEE 评审数据库接入层

非阻塞: 所有 record_*() 调用通过 queue.Queue + 后台 daemon thread,
主调用方 (see-*.py / failure_analyzer) 立即返回。

设计原则:
- 配置缺失 (REVIEW_DB_HOST 未设) 时所有钩子静默 no-op, 不阻塞流水线
- basicConfig 不在这里调用 (避免与 infra/core/failure_analyzer/cli.py 冲突)
- DDL 来源: ddl/*.sql (已被 git 跟踪)
"""
from __future__ import annotations

from typing import Optional

_logger = __import__("logging").getLogger(__name__)

_client_singleton: "Optional[ReviewDbClient]" = None


def get_client():
    """获取进程级单例; 配置缺失或 REVIEW_DB_DISABLED=1 时返回 None."""
    global _client_singleton
    if _client_singleton is not None:
        return _client_singleton

    # 二次幂等
    import os

    if os.environ.get("REVIEW_DB_DISABLED", "").strip() in ("1", "true", "yes", "on"):
        _logger.debug("review_db disabled via REVIEW_DB_DISABLED")
        return None

    from .config import ReviewDbConfig
    cfg = ReviewDbConfig.from_env()
    if cfg is None:
        _logger.debug("review_db config missing (REVIEW_DB_HOST unset); hooks no-op")
        return None

    from .client import ReviewDbClient
    _client_singleton = ReviewDbClient(cfg)
    _client_singleton.start()
    return _client_singleton


def flush(timeout: float = 10.0) -> bool:
    """等待队列清空. 给需要在脚本退出前确保数据落盘的调用方用."""
    c = get_client()
    if c is None:
        return True
    return c.flush(timeout=timeout)


def shutdown(timeout: float = 10.0) -> None:
    """flush + 关闭 worker. 单次进程生命周期结束时调用一次即可."""
    global _client_singleton
    if _client_singleton is None:
        return
    try:
        _client_singleton.shutdown(timeout=timeout)
    finally:
        _client_singleton = None
