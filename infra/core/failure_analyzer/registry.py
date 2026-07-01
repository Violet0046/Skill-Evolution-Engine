"""
registry.py —— 工具名 → 函数 注册表

双入口（cli.py + schemas.py）共享同一份代码：

    # CLI 入口
    cli.main() → argparse → 查 REGISTRY → 调用函数

    # LLM tool_use 入口
    TOOL_SCHEMAS 列表 → claude_api.create_message(tools=[...])
    → LLM 决定调哪个 → 查 REGISTRY → 调用函数

懒加载：避免循环依赖，启动开销最小。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# name → 实际函数（首次 resolve 时填充）
REGISTRY: Dict[str, Optional[Callable[..., Any]]] = {
    "see_failure_overview": None,
    "see_find_by_pattern": None,
    "see_entry_detail": None,
}


def resolve(name: str) -> Callable[..., Any]:
    """按名取函数（懒加载）。

    找不到时抛 KeyError（编程错误，不是工具错误）。
    """
    if name not in REGISTRY:
        raise KeyError(f"unknown tool: {name}. Available: {list(REGISTRY.keys())}")

    fn = REGISTRY[name]
    if fn is None:
        # 懒加载
        if name == "see_failure_overview":
            from .failure_overview import see_failure_overview
            fn = see_failure_overview
        elif name == "see_find_by_pattern":
            from .failures_by_pattern import see_find_by_pattern
            fn = see_find_by_pattern
        elif name == "see_entry_detail":
            from .failure_detail import see_entry_detail
            fn = see_entry_detail
        REGISTRY[name] = fn
        logger.debug(f"懒加载工具: {name} → {fn.__name__}")
    return fn


def list_tools() -> List[str]:
    """列出所有可用工具名。"""
    return list(REGISTRY.keys())
