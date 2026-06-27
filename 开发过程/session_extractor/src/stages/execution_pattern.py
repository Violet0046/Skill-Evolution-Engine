"""execution_pattern stage — step_counts / tool_distribution / phase_durations。

从 entries + state_machine.transitions 推算 4 个统计字段。
retry_loops 暂留空，v5 retry_chain detector 启用时填充。

"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def compute_execution_pattern(
    entries: List[Dict[str, Any]],
    state_machine: Dict[str, Any],
) -> Dict[str, Any]:
    """从 entries + state_machine 统计行为模式。

    返回：
    - step_counts: {entry_class: count}
    - retry_loops: [] （v5 占位）
    - tool_distribution: {tool_name: count}（仅 ai_tool_call 的 name）
    - phase_durations: {phase: {start, end}}（从 state_machine.transitions 推导）
    """
    step_counts: Counter = Counter()
    tool_distribution: Counter = Counter()
    retry_loops: List[Dict[str, Any]] = []
    phase_durations: Dict[str, Dict[str, str]] = {}

    # step_counts：按 entry_class
    for e in entries:
        cls = e.get("entry_class", "")
        if cls:
            step_counts[cls] += 1

    # tool_distribution：从 ai_tool_call 提 name
    for e in entries:
        if e.get("entry_class") != "ai_tool_call":
            continue
        content = (e.get("message", {}) or {}).get("content", []) or []
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict):
                name = item.get("name", "")
                if name:
                    tool_distribution[name] += 1

    # phase_durations：从 state_machine.transitions 推导
    transitions = state_machine.get("transitions", []) if isinstance(state_machine, dict) else []
    for t in transitions:
        if not isinstance(t, dict):
            continue
        phase = t.get("phase")
        at = t.get("at")
        if not phase or not at:
            continue
        if phase not in phase_durations:
            phase_durations[phase] = {"start": at, "end": at}
        else:
            phase_durations[phase]["end"] = at

    return {
        "step_counts": dict(step_counts),
        "retry_loops": retry_loops,  # 暂留空，复用 v5 retry_chain 检测
        "tool_distribution": dict(tool_distribution),
        "phase_durations": phase_durations,
    }