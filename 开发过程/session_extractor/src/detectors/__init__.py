"""
detector 注册表入口。

调用 run_all(entries, ctx, enabled=None) 即可执行所有（或指定）detector。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.models import ClassifiedEntry, DetectorContext
from .base import Detector, get_all, register


def run_all(
    entries: List[ClassifiedEntry],
    ctx: DetectorContext,
    enabled: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """执行所有（或指定）detector，返回 {detector_name: [events...]}。"""
    registry = get_all()
    target = enabled if enabled is not None else list(registry.keys())

    out: Dict[str, List[Dict[str, Any]]] = {}
    for name in target:
        cls = registry.get(name)
        if cls is None:
            continue
        out[name] = cls().run(entries, ctx)
    return out


# 注册表在子模块 import 时自动填充；此处显式 import 触发 @register
def _import_all() -> None:
    """触发各 detector 子模块的 @register；缺失模块在步骤 4-8 补齐前静默跳过。"""
    for mod in ("state_machine", "gate", "review_contract", "user_confirmation", "symlink"):
        try:
            __import__(f"src.detectors.{mod}", fromlist=["*"])
        except ImportError:
            # 该 detector 模块尚未实现；get_all() 返回当前已注册的部分
            pass


_import_all()