"""
symlink detector — 接口骨架。

对每条带 cwd 的 entry，调 os.path.realpath 与 logical cwd 比较，不一致即视为
"跳到物理源"事件。1b4c0c37 真实样本 single-cwd → 此 detector 在真实样本上 0 命中；
v5 拿到 multi-cwd 数据后可启用。

用 ctx.cwd_realpath_cache 缓存 realpath 结果，避免重复 stat。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from src.models import ClassifiedEntry, DetectorContext, SymlinkHopEvent
from .base import Detector, register


@register("symlink")
class SymlinkHopDetector(Detector):
    """cwd 物理源判定（symlink/junction 跳变）。"""

    def run(
        self,
        entries: List[ClassifiedEntry],
        ctx: DetectorContext,
    ) -> List[Dict[str, Any]]:
        cache = ctx.cwd_realpath_cache
        out: List[SymlinkHopEvent] = []

        for e in entries:
            cwd = e.raw.get("cwd")
            if not isinstance(cwd, str) or not cwd:
                continue

            if cwd in cache:
                real = cache[cwd]
            else:
                try:
                    real = os.path.realpath(cwd)
                except OSError:
                    real = cwd
                cache[cwd] = real

            if real != cwd:
                out.append(SymlinkHopEvent(
                    kind="symlink_hop",
                    logical_cwd=cwd,
                    physical_cwd=real,
                    evidence_ref=e.uuid() or "",
                    at=e.timestamp(),
                ))

        return [e.to_dict() for e in out]