"""
user_confirmation detector — 识别 AskUserQuestion 触发 / [auto-confirm] 标记 / 中断。

触发条件：
- entry_class == "user_input"
  - message.content[*].text 含 "[Request interrupted...]" → mode="interrupted"
  - message.content[*].text 含 "[auto-confirm]" → mode="auto_confirm"
- entry.permissionMode 显式设置 → mode="explicit_<pm>"
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.models import ClassifiedEntry, DetectorContext, UserConfirmationEvent
from .base import Detector, register


_INTERRUPTED_RE = re.compile(r"\[Request interrupted[^\]]*\]", re.IGNORECASE)
_AUTO_CONFIRM_MARKER = "[auto-confirm]"


@register("user_confirmation")
class UserConfirmationDetector(Detector):
    """用户确认 / 自动确认 / 中断事件检测。"""

    def run(
        self,
        entries: List[ClassifiedEntry],
        ctx: DetectorContext,
    ) -> List[Dict[str, Any]]:
        # AUTO_CONFIRM 来源：env 优先，spec.environment.auto_confirm_keys 次之
        env_keys = ["AUTO_CONFIRM", "AUTO_CONFIRM_USER_CONFIRMATION"]
        spec_keys = []
        if isinstance(ctx.spec, dict):
            spec_keys = ((ctx.spec.get("environment") or {}).get("auto_confirm_keys") or [])
        all_keys = list(env_keys) + list(spec_keys)
        auto_confirm_env = next((ctx.env[k] for k in all_keys if k in ctx.env), None)

        out: List[UserConfirmationEvent] = []

        for e in entries:
            if e.entry_class != "user_input":
                continue
            text = self._extract_text(e.raw)
            if not text:
                # 检查 permissionMode
                pm = e.raw.get("permissionMode")
                if isinstance(pm, str) and pm:
                    out.append(UserConfirmationEvent(
                        kind="user_confirmation",
                        mode=f"explicit_{pm}",
                        trigger="permissionMode",
                        evidence_ref=e.uuid() or "",
                        at=e.timestamp(),
                        auto_confirm_env=auto_confirm_env,
                    ))
                continue

            if _INTERRUPTED_RE.search(text):
                out.append(UserConfirmationEvent(
                    kind="user_confirmation",
                    mode="interrupted",
                    trigger="[Request interrupted...]",
                    evidence_ref=e.uuid() or "",
                    at=e.timestamp(),
                    auto_confirm_env=auto_confirm_env,
                ))
                continue

            if _AUTO_CONFIRM_MARKER.lower() in text.lower():
                out.append(UserConfirmationEvent(
                    kind="user_confirmation",
                    mode="auto_confirm",
                    trigger=_AUTO_CONFIRM_MARKER,
                    evidence_ref=e.uuid() or "",
                    at=e.timestamp(),
                    auto_confirm_env=auto_confirm_env,
                ))
                continue

            # permissionMode 在 user_input 上同时存在时
            pm = e.raw.get("permissionMode")
            if isinstance(pm, str) and pm:
                out.append(UserConfirmationEvent(
                    kind="user_confirmation",
                    mode=f"explicit_{pm}",
                    trigger="permissionMode",
                    evidence_ref=e.uuid() or "",
                    at=e.timestamp(),
                    auto_confirm_env=auto_confirm_env,
                ))

        return [e.to_dict() for e in out]

    @staticmethod
    def _extract_text(raw: Dict[str, Any]) -> str:
        """从 user_input 的 message.content 提取文本。"""
        content = (raw.get("message", {}) or {}).get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    t = item.get("text", "")
                    if isinstance(t, str):
                        parts.append(t)
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts)
        return ""