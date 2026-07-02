"""
schemas.py —— LLM tool_use schema 定义

每个 schema 对应一个 see_* 工具函数，可直接传入 Anthropic SDK 的
`messages.create(tools=[...])` 参数。

格式遵循 Anthropic tool_use 规范：
{
    "name": "see_xxx",
    "description": "...",
    "input_schema": {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
}

设计原则：
- description 写**人话**（让 LLM 决定何时调），不写 API 细节
- input_schema 字段尽量少（避免 LLM 拼错）
- required 标最关键的，optional 字段都给默认值
"""
from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Tool 1: see_failure_overview
# ---------------------------------------------------------------------------

SEE_FAILURE_OVERVIEW_SCHEMA: Dict[str, Any] = {
    "name": "see_failure_overview",
    "description": (
        "获取指定 session 的失败概览，按 by_pattern（失败模式）+ by_agent_type（agent 类型）"
        "两维聚合失败计数，附带 top-N 失败模式（含 uuid 列表）。用于分析失败的"
        "第一步：先看全貌，再决定深入哪类错误。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session UUID，例如 5527b413-affc-443e-862f-15ff6bb3f7d1",
            },
            "root": {
                "type": "string",
                "description": "简化版数据根目录（可选，默认 ../projects-simplified）",
            },
            "top_n_patterns": {
                "type": "integer",
                "description": "top_patterns 列表上限，默认 10",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["session_id"],
    },
}


# ---------------------------------------------------------------------------
# Tool 2: see_find_by_pattern
# ---------------------------------------------------------------------------

SEE_FIND_BY_PATTERN_SCHEMA: Dict[str, Any] = {
    "name": "see_find_by_pattern",
    "description": (
        "按 tool_name:error[:80] 失败模式 key 找出所有匹配的 tool_result entry。"
        "返回 hit 列表（4 字段：uuid / agent_type / timestamp / error_excerpt）。"
        "find 是中观浏览工具：让 LLM 在不爆 context 的前提下扫描一类失败。"
        "完整上下文（input_params / reasoning 等）请用 see_entry_detail。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session UUID",
            },
            "pattern": {
                "type": "string",
                "description": "失败模式 key，格式 'ToolName:error[:80]'",
            },
            "root": {
                "type": "string",
                "description": "简化版数据根目录（可选）",
            },
            "limit": {
                "type": "integer",
                "description": "返回 hit 数量上限（默认 20，最大 100）",
                "default": 20,
                "minimum": 1,
                "maximum": 100,
            },
            "include_subagents": {
                "type": "boolean",
                "description": "是否包含 subagent 命中（默认 True）",
                "default": True,
            },
        },
        "required": ["session_id", "pattern"],
    },
}


# ---------------------------------------------------------------------------
# Tool 3: see_entry_detail
# ---------------------------------------------------------------------------

SEE_ENTRY_DETAIL_SCHEMA: Dict[str, Any] = {
    "name": "see_entry_detail",
    "description": (
        "按 (session_id, uuid) 取出单条工具调用失败的完整上下文（5 字段，按时间序 T1→T2→T3→T4）：\n"
        "  - reasoning_before (T1): 模型事前计划\n"
        "  - tool_name (T2): 工具名\n"
        "  - input_params (T2): 调用参数\n"
        "  - error_output (T3): 失败信息（成功为 null）\n"
        "  - reasoning_after (T4): 模型事后归因\n"
        "是失败分析'最深度'的查询入口。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session UUID",
            },
            "uuid": {
                "type": "string",
                "description": "目标 entry 的 uuid（通常从 see_find_by_pattern 的 hits 拿）",
            },
            "root": {
                "type": "string",
                "description": "简化版数据根目录（可选）",
            },
            "raw_root": {
                "type": "string",
                "description": "原始版数据根目录（use_raw=True 时使用）",
            },
            "use_raw": {
                "type": "boolean",
                "description": "True 时从原始未 simplify 数据取（拿到完整 toolUseResult）",
                "default": False,
            },
            "include_reasoning_before": {
                "type": "boolean",
                "description": "是否包含 reasoning_before（模型事前计划，默认 True）",
                "default": True,
            },
            "include_reasoning_after": {
                "type": "boolean",
                "description": "是否包含 reasoning_after（模型事后归因，默认 True）",
                "default": True,
            },
        },
        "required": ["session_id", "uuid"],
    },
}


# ---------------------------------------------------------------------------
# 列表导出
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    SEE_FAILURE_OVERVIEW_SCHEMA,
    SEE_FIND_BY_PATTERN_SCHEMA,
    SEE_ENTRY_DETAIL_SCHEMA,
]


__all__ = [
    "SEE_FAILURE_OVERVIEW_SCHEMA",
    "SEE_FIND_BY_PATTERN_SCHEMA",
    "SEE_ENTRY_DETAIL_SCHEMA",
    "TOOL_SCHEMAS",
]
