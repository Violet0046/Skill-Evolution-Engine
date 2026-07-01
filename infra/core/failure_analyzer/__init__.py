"""
see-tools —— 失败分析 LLM 工具集

背景：
  Skill-Evolution-Engine 在 see-analyze / see-evolve 阶段，需要让 LLM
  看到 Claude Code session 里的失败信息。但一个 7 小时的"需求分析 agent"
  session 就有 2,398 条 entry / 685 次工具调用 / 27 个错误，把整份 trace
  塞给 LLM 会爆上下文窗口。本工具集用 Python 代码**预定位**错误位置，
  暴露一组**按需查询**工具，让 LLM 自助调取。

模块组织：
  _common/
    session_reader.py  —— 双格式 entry 迭代器（JSON-array / NDJSON）
    index_store.py     —— 预建失败索引（懒构建 + mtime 失效）
    errors.py          —— 统一 ToolError 与 JSON 友好输出
  failure_overview.py  —— see_failure_overview（按 session/skill/tool/phase 四维概览）
  find_by_pattern.py   —— see_find_by_pattern（按 tool_name:error[:80] 模式匹配）
  entry_detail.py      —— see_entry_detail（取单条 entry 完整上下文，含 use_raw 回退）
  context_window.py    —— see_context_window（批 2：本批未实现）
  retry_chain.py       —— see_retry_chain（批 2：本批未实现）
  subagent_timeline.py —— see_subagent_timeline（批 2：本批未实现）
  failure_by_skill.py  —— see_failure_by_skill（批 3：本批未实现）

入口：
  registry.py  —— name → function 注册表（双入口共享）
  cli.py       —— `python -m src.failure_analyzer <cmd> <args>` 形式 CLI（Bash 调用）
  schemas.py   —— `TOOL_SCHEMAS` 列表（直接给 Anthropic tool_use API 消费）

数据约定：
  索引位置：<simplified_root>/.index/<session_id>.json
  主文件：  <simplified_root>/<session_id>.jsonl  (实际为 JSON 数组，800 条左右)
  子文件：  <simplified_root>/<session_id>/subagents/agent-<id>.jsonl  (NDJSON)

调用风格：
  - 不抛异常（除编程错误外）。session_id/uuid 找不到时返 {"error": "..."}。
  - 退出码恒为 0（让 LLM 不要把"找不到"当 fatal）。
  - 返回 JSON 顶层统一为 dict（不是 list），方便 LLM 按字段引用。
"""

from __future__ import annotations

from .registry import REGISTRY, list_tools, resolve
from .schemas import TOOL_SCHEMAS

# 顶层导出：方便 `from src.failure_analyzer import see_failure_overview`
from .failure_overview import see_failure_overview  # noqa: F401
from .failures_by_pattern import see_find_by_pattern  # noqa: F401
from .failure_detail import see_entry_detail  # noqa: F401

__all__ = [
    # 注册表 + 工具函数
    "REGISTRY",
    "list_tools",
    "resolve",
    # 三个工具函数
    "see_failure_overview",
    "see_find_by_pattern",
    "see_entry_detail",
    # LLM tool_use schema
    "TOOL_SCHEMAS",
]
