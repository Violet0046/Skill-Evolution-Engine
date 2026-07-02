"""
failure_overview.py —— see_failure_overview 工具

用途：
  给 LLM 一个"先看全貌"的入口——返回 session 的 stats + top-N 失败模式。

设计取舍：
  - 不返 by_skill / by_phase / by_tool / by_agent_type（v1.1 索引已删除这些字段）
  - 失败模式本身是"tool_name:error[:80]"，LLM 从中能直接读出工具名
  - 真正有用的维度是"哪些错误出现最多"，全部已在 by_pattern 里

输出示例：
{
  "session_id": "5527b413-...",
  "summary": {
    "total_entries": 2417,
    "total_errors": 27,
    "main_errors": 4,
    "sub_errors": 23,
    "subagent_files": 36,
    "session_duration_hours": 7.04
  },
  "top_patterns": [
    {
      "pattern": "Bash:Exit code 1",
      "count": 8,
      "uuids": ["...", "..."]
    },
    ...
  ]
}

参数：
  session_id:     session UUID（必填）
  root:           简化版数据根目录（默认 ../projects-simplified）
  top_n_patterns: top_patterns 列表长度上限（默认 10）

返回：
  - 正常：业务 dict（无 error 字段）
  - 找不到 session：{"error": "session not found: <sid>", "session_id": "..."}
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .common.errors import err
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
    top_n_patterns: int = 10,
    refresh: bool = False,
) -> Dict[str, Any]:
    """see_failure_overview 主入口。

    参数：
        session_id:     session UUID
        root:           简化版数据根目录
        top_n_patterns: top_patterns 列表上限
        refresh:        True 时强制重建索引（默认 False，懒构建）
    """
    if root is None:
        # 默认：项目根/evidence/projects-simplified
        root = str(Path(__file__).resolve().parents[3] / "evidence" / "projects-simplified")

    # 1) 校验 session 存在
    main_path = Path(root) / f"{session_id}.jsonl"
    if not main_path.exists():
        return err(f"session not found: {session_id}", session_id=session_id, root=root)

    # 2) 加载/构建索引
    try:
        idx = SessionIndex(session_id, root)
        if refresh:
            idx.invalidate()
        data = idx.load()
    except Exception as e:
        logger.exception(f"索引构建失败: {session_id}")
        return err(f"index build failed: {type(e).__name__}: {e}", session_id=session_id)

    # 3) 组装 summary
    stats = data.get("stats", {})
    summary = dict(stats)
    summary["session_duration_hours"] = _compute_session_duration_hours(session_id, root)

    # 4) top_patterns（by_pattern 已按 count desc 排序）
    by_pattern = data.get("by_pattern", {})
    top_patterns: list = []
    for i, (pat, info) in enumerate(by_pattern.items()):
        if i >= top_n_patterns:
            break
        top_patterns.append({
            "pattern": pat,
            "count": info.get("count", 0),
            "uuids": info.get("uuids", []),
        })

    return {
        "session_id": session_id,
        "agent_cwd": _load_agent_cwd(root, session_id),
        "summary": summary,
        "top_patterns": top_patterns,
        "by_agent_type": [
            {
                "agent_type": atype,
                "errors": info.get("errors", 0),
                "share": round(info.get("errors", 0) / (summary.get("total_errors") or 1), 3),
            }
            for atype, info in data.get("by_agent_type", {}).items()
        ],
    }


def _load_agent_cwd(root: str, session_id: str) -> str | None:
    """从 session header 拿 agent_cwd（session 启动时的工作目录 = agent 项目根）。"""
    from .common.session_reader import load_main_session
    header, _ = load_main_session(root, session_id)
    if not isinstance(header, dict):
        return None
    return header.get("cwd")
