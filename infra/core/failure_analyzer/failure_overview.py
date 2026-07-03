"""
failure_overview.py —— see_failure_overview 工具

用途：
  预热 `.index/<sid>.json`（懒构建）+ 触发索引构建。
  失败 raise RuntimeError（**不**返 dict）。

设计取舍：
  - 按 agent 入手（sub-agent 用 find 查某 agent 的所有 hit，detail 看具体）
  - 不按 tool:error 模式分（v1 删 by_pattern）
  - **不**返 bundle dict——**只**做"写 .index/"的副作用；返回 None

成功：return（隐式 None）。失败：raise RuntimeError（**带**错误信息）。

参数：
  session_id:     session UUID（必填）
  root:           简化版数据根目录（默认 ../projects-simplified）
  refresh:        True 时强制重建索引（默认 False，懒构建）
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .common.index_store import SessionIndex
from .common.session_reader import collect_all_entries

logger = logging.getLogger(__name__)


def _parse_iso_ts(ts: str):
    """宽松解析 ISO 时间戳；失败返 None。"""
    if not ts:
        return None
    s = ts.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _compute_session_duration_hours(session_id: str, root: str) -> float:
    """计算 session 起止时间差（小时）。失败返 0.0。"""
    all_entries = collect_all_entries(root, session_id)
    timestamps = [e.get("timestamp") for e in all_entries if e.get("timestamp")]
    if not timestamps:
        return 0.0
    parsed = [_parse_iso_ts(t) for t in timestamps]
    parsed = [p for p in parsed if p is not None]
    if not parsed:
        return 0.0
    delta = max(parsed) - min(parsed)
    return round(delta.total_seconds() / 3600, 2)


def see_failure_overview(
    session_id: str,
    root: str | None = None,
    refresh: bool = False,
) -> None:
    """see_failure_overview 主入口。

    成功：return（隐式 None）。
    失败：raise RuntimeError（**带**错误信息）。

    副作用：写 `.index/<session_id>.json`（懒构建）。
    """
    if root is None:
        # 默认：项目根/evidence/projects-simplified
        root = str(Path(__file__).resolve().parents[3] / "evidence" / "projects-simplified")

    # 1) 校验 session 存在
    main_path = Path(root) / f"{session_id}.jsonl"
    if not main_path.exists():
        raise RuntimeError(f"session not found: {session_id} (root={root})")

    # 2) 加载/构建索引（**副作用**：写 .index/<session_id>.json）
    try:
        idx = SessionIndex(session_id, root)
        if refresh:
            idx.invalidate()
        idx.load()
    except Exception as e:
        logger.exception(f"索引构建失败: {session_id}")
        raise RuntimeError(f"index build failed: {type(e).__name__}: {e}") from e

    # 成功：return（隐式 None）


def _load_agent_cwd(root: str, session_id: str) -> str | None:
    """从 session header 拿 agent_cwd（session 启动时的工作目录 = agent 项目根）。"""
    from .common.session_reader import load_main_session
    header, _ = load_main_session(root, session_id)
    if not isinstance(header, dict):
        return None
    return header.get("cwd")
