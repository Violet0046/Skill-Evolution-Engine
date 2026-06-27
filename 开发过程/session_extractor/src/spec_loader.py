"""
agent_spec 加载器 — 加载 specs/{spec,hooks,subagents,constraints}.yaml，
合并为单一 dict 供 detector 使用。

缺省行为：
- 目录不存在 → 返空 dict
- 文件缺失 → 该文件对应 key 不出现
- YAML 解析失败 → 记录警告 + 返空 dict（不让 collector 崩溃）
"""

from __future__ import annotations

import os
from typing import Any, Dict

try:
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False


def load_spec(spec_dir: "str | None") -> Dict[str, Any]:
    """加载 agent_spec YAML 目录。

    返回的 dict 形如：
    {
        "spec": {...},         # specs/spec.yaml
        "hooks": {...},        # specs/hooks.yaml
        "subagents": {...},    # specs/subagents.yaml
        "constraints": [...],  # specs/constraints.yaml
    }
    """
    if not spec_dir or not os.path.isdir(spec_dir):
        return {}

    if not _HAS_YAML:
        return {}

    out: Dict[str, Any] = {}
    for key, filename in (
        ("spec", "spec.yaml"),
        ("hooks", "hooks.yaml"),
        ("subagents", "subagents.yaml"),
        ("constraints", "constraints.yaml"),
    ):
        path = os.path.join(spec_dir, filename)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                out[key] = data
            else:
                out[key] = data  # 允许 list（constraints.yaml）
        except (yaml.YAMLError, OSError, UnicodeDecodeError):
            # 解析失败时静默跳过该文件
            continue

    return out