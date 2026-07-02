"""
failures_by_pattern.py —— see_find_by_pattern 工具

用途：
  按 `tool_name:error[:80]` 模式 key 找出所有匹配的 tool_result entry。

  与 see_failure_overview 的区别：overview 给"模式 → 计数 + uuid 列表"
  摘要；本工具给"模式 → 完整 hit 列表（含 agent_id / skill / timestamp /
  error_excerpt）"，便于 LLM 一次拿到足够上下文决定深入哪条。

  LLM 典型用法：
  1. 先 see_failure_overview 看到 "Bash:No module named requests" 7 次
  2. 调 see_find_by_pattern 取 7 个 hit
  3. 选 1-2 个 hit 调 see_entry_detail 看完整 traceback

参数：
  session_id:        session UUID
  pattern:           tool_name:error[:80]（必填，可从 see_failure_overview 复制）
  root:              简化版数据根目录
  limit:             返回上限（默认 20，最大 100）
  include_subagents: 是否包含 subagent 命中（默认 True）

输出示例：
{
  "session_id": "...",
  "pattern": "Bash:No module named requests",
  "matched": 7,
  "hits": [
    {
      "uuid": "dbad6dda-...",
      "agent_id": null,           # 主流程
      "source": "main",
      "skill": "phase1-requirement-clarify",
      "phase": "phase1",
      "timestamp": "2026-06-17T01:54:05.272Z",
      "error_first_line": "ImportError: No module named requests",
      "error_excerpt": "Error: Exit code 1\nTraceback (most recent call last):\n  File \".claude/skills/查询需求信息/scripts/query_simple.py\", line 10\n    import requests\nImportError: No module named requests"
    },
    {
      "uuid": "61be7587-...",
      "agent_id": "a1cd7b2c3f94f91b6",
      "source": "subagent:a1cd7b2c3f94f91b6",
      "skill": "查询需求信息",
      "phase": null,
      "timestamp": "2026-06-17T06:07:49.648Z",
      "error_first_line": "ImportError: No module named requests",
      "error_excerpt": "..."
    }
  ]
}

返回：
  - 正常：业务 dict
  - 找不到 session：{"error": "session not found: ..."}
  - 找不到 pattern：{"matched": 0, "hits": [], ...}（**不**是错误，返空结果）
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .common.errors import err
from .common.index_store import SessionIndex
from .common.session_reader import collect_all_entries

logger = logging.getLogger(__name__)


def _extract_error_excerpt(entry: Dict[str, Any], max_len: int = 600) -> str:
    """取 entry 错误完整文本（截断到 max_len 字符，UTF-8 安全）。"""
    content = entry.get("message", {}).get("content", [])
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict):
            err_text = item.get("content", "") or ""
            if err_text:
                return err_text[:max_len]
    tur = entry.get("toolUseResult")
    if isinstance(tur, str):
        return tur[:max_len]
    return ""


def see_find_by_pattern(
    session_id: str,
    pattern: str,
    root: str | None = None,
    limit: int = 20,
    include_subagents: bool = True,
) -> Dict[str, Any]:
    """see_find_by_pattern 主入口。

    v1.7 优化：hit 只返 4 字段（uuid / agent_type / timestamp / error_excerpt）。
    find 是中观浏览工具：让 LLM 在不爆 context 的前提下浏览一类失败。
    详情（input_params / reasoning 等）留给 detail。
    """
    if root is None:
        root = str(Path(__file__).resolve().parents[3] / "evidence" / "projects-simplified")

    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

    # 1) session 存在性
    main_path = Path(root) / f"{session_id}.jsonl"
    if not main_path.exists():
        return err(f"session not found: {session_id}", session_id=session_id, root=root)

    # 2) 拿 pattern 对应 uuid 三元组
    try:
        idx = SessionIndex(session_id, root)
        index_data = idx.load()
    except Exception as e:
        logger.exception(f"索引加载失败: {session_id}")
        return err(f"index load failed: {type(e).__name__}: {e}", session_id=session_id)

    bucket = index_data.get("by_pattern", {}).get(pattern)
    if not bucket:
        return {
            "session_id": session_id,
            "pattern": pattern,
            "matched": 0,
            "hits": [],
        }

    candidate_records: List[Dict[str, Any]] = bucket.get("uuids", [])

    # 3) 一次性加载 entries（取 timestamp + error_excerpt）
    all_entries = collect_all_entries(root, session_id)
    entry_by_uuid: Dict[str, Dict[str, Any]] = {}
    for e in all_entries:
        u = e.get("uuid")
        if u:
            entry_by_uuid[u] = e

    # 4) 组装 hits（v1.7：只返 4 字段）
    hits: List[Dict[str, Any]] = []
    for rec in candidate_records:
        if len(hits) >= limit:
            break
        u = rec.get("uuid")
        agent_id = rec.get("agent_id")
        # source 从 agent_id 推导（仅用于 include_subagents 过滤，不入 hit 字段）
        source = "main" if agent_id is None else "subagent"
        agent_type = rec.get("agent_type", "main")
        if not include_subagents and source != "main":
            continue

        e = entry_by_uuid.get(u) if u else None
        if not e:
            continue

        hits.append({
            "uuid": u,                                      # 用于 drill into detail
            "agent_type": agent_type,                        # 语义化分组
            "timestamp": e.get("timestamp"),                 # 时间序
            "error_excerpt": _extract_error_excerpt(e),       # 理解错误（150 字符左右）
        })

    return {
        "session_id": session_id,
        "pattern": pattern,
        "matched": bucket.get("count", 0),
        "returned": len(hits),
        "hits": hits,
    }
