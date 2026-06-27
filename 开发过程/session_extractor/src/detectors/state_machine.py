"""
state_machine detector — 从 attachment.hook_success 的 attachment.command 字段
提取 phase 转移轨迹。

默认正则：`^phase(\d+)\s+(pre|post)-([a-z0-9\-]+)`，匹配：
- "phase0 pre-init workdir"
- "phase2 pre-subagent"
- "phase3 post-subagent-review"
- "phase4 post-summary"

spec 存在时（spec.phases[].roles 列表）可覆盖正则；缺省走 fallback。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.models import ClassifiedEntry, DetectorContext, PhaseTransition
from .base import Detector, register


# 默认正则：phaseN pre|post action-name
_DEFAULT_PHASE_RE = re.compile(
    r"^phase(\d+)\s+(pre|post)-([a-z0-9\-]+)", re.IGNORECASE
)


@register("state_machine")
class StateMachineDetector(Detector):
    """phase 状态轨迹重建 detector。"""

    def run(
        self,
        entries: List[ClassifiedEntry],
        ctx: DetectorContext,
    ) -> List[Dict[str, Any]]:
        phase_re = self._compile_phase_re(ctx.spec)
        transitions: List[PhaseTransition] = []
        seen_phases: List[str] = []

        for e in entries:
            if e.entry_class != "attachment.hook_success":
                continue
            cmd = (e.raw.get("attachment", {}) or {}).get("command", "") or ""
            m = phase_re.search(cmd.strip())
            if not m:
                continue
            phase = self._resolve_phase_name(m, ctx.spec)
            # role = 从 group(2) 起始位置截取整段（如 "phase0 pre-init workdir" → "pre-init workdir"）
            role = cmd.strip()[m.start(2):].strip().lower()
            transitions.append(
                PhaseTransition(
                    phase=phase,
                    hook_event=(e.raw.get("attachment", {}) or {}).get("hookEvent", ""),
                    trigger_entry_uuid=e.uuid() or "",
                    trigger_attachment_command=cmd.strip(),
                    trigger_hook_name=(e.raw.get("attachment", {}) or {}).get("hookName"),
                    at=e.timestamp(),
                    role=role,
                )
            )
            if phase not in seen_phases:
                seen_phases.append(phase)

        # unexpected_exits：所有 transitions 中后一条与前一条 phase 不同但中间没有其他 phase 的
        # 简单启发：相邻 transitions 的 phase 名称集合若跳跃超过 1 视为 unexpected
        unexpected_exits = self._detect_unexpected_exits(transitions)

        # 用单一 dict 输出，与 plan 一致；phases 字段保持 list[str]
        return [
            {
                "kind": "state_machine",
                "phases": seen_phases,
                "transitions": [t.to_dict() for t in transitions],
                "unexpected_exits": [u.to_dict() for u in unexpected_exits],
            }
        ]

    @staticmethod
    def _compile_phase_re(spec: Dict[str, Any]) -> "re.Pattern[str]":
        """根据 spec.phases 编译 phase 正则。spec 缺省或解析失败时用默认正则。"""
        phases = spec.get("phases") if isinstance(spec, dict) else None
        if not isinstance(phases, list) or not phases:
            return _DEFAULT_PHASE_RE
        # 收集所有 spec 中声明的 phase 名前缀（如 "phase0" / "phase1"）
        names: List[str] = []
        for p in phases:
            if isinstance(p, dict):
                name = p.get("name")
                if isinstance(name, str):
                    names.append(name)
            elif isinstance(p, str):
                names.append(p)
        if not names:
            return _DEFAULT_PHASE_RE
        # 转义后用 | 拼接
        alt = "|".join(re.escape(n) for n in names)
        # 形如 (phase0|phase1|phase2)\s+(pre|post)-...
        pattern = rf"^({alt})\s+(pre|post)-([a-z0-9\-]+)"
        return re.compile(pattern, re.IGNORECASE)

    @staticmethod
    def _resolve_phase_name(m: "re.Match[str]", spec: Dict[str, Any]) -> str:
        """根据正则匹配结果 + spec 决定 phase 名。

        - 默认正则（spec 缺省）：m.group(1) 是数字 → "phaseN"
        - spec 模式：m.group(1) 已经是完整 phase 名（"phase0" 等），直接使用
        """
        token = m.group(1)
        if isinstance(spec, dict) and spec.get("phases"):
            return token  # spec 模式下 group(1) 已是 spec 中的 name
        return f"phase{token}"

    @staticmethod
    def _detect_unexpected_exits(
        transitions: List[PhaseTransition],
    ) -> List[PhaseTransition]:
        """检测相邻 transitions 之间 phase 跳跃 > 1 的边界。

        例：phase0 → phase2（跳过 phase1）→ transition[phase0] 视为 unexpected_exit。
        """
        if len(transitions) < 2:
            return []
        unexpected: List[PhaseTransition] = []
        for prev, curr in zip(transitions, transitions[1:]):
            prev_n = _phase_number(prev.phase)
            curr_n = _phase_number(curr.phase)
            if prev_n is None or curr_n is None:
                continue
            if abs(curr_n - prev_n) > 1:
                unexpected.append(prev)
        return unexpected


def _phase_number(phase: str) -> "int | None":
    """phase0..phase9 → 0..9；其他返 None。"""
    m = re.match(r"^phase(\d+)$", phase, re.IGNORECASE)
    return int(m.group(1)) if m else None