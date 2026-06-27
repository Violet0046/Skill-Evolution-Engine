"""
detector 抽象基类 + @register 装饰器 + expand_full_ref 接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from src.models import ClassifiedEntry, DetectorContext


_REGISTRY: Dict[str, type] = {}


def register(name: str) -> Callable[[type], type]:
    """类装饰器：把 Detector 子类注册到全局 _REGISTRY。"""

    def deco(cls: type) -> type:
        _REGISTRY[name] = cls
        cls.DETECTOR_NAME = name
        return cls

    return deco


def get_all() -> Dict[str, type]:
    """返回当前已注册 detector 的快照（dict 副本，避免外部修改）。"""
    return dict(_REGISTRY)


class Detector(ABC):
    """detector 抽象基类。所有 detector 必须实现 run()。"""

    DETECTOR_NAME: str = ""

    @abstractmethod
    def run(
        self,
        entries: List[ClassifiedEntry],
        ctx: DetectorContext,
    ) -> List[Dict[str, Any]]:
        """返回该 detector 检测到的事件 dict 列表。空列表表示 0 命中。"""

    def expand_full_ref(
        self,
        evidence_ref: str,
        raw_entries: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """根据 evidence_ref（uuid）在原始未简化 entries 中查找。

        detector 命中需要全文时由上层调用；pipeline 默认不调用。
        """
        for e in raw_entries:
            if isinstance(e, dict) and e.get("uuid") == evidence_ref:
                return e
        return None