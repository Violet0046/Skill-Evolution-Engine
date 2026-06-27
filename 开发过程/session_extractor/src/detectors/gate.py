"""
gate detector — 识别 *-gate.mjs / phase*-pre-* 拒答事件。

支持 4 种 hook subtype：
1. attachment.hook_success — exitCode != 0（核心：hook 阻断错误）
2. attachment.async_hook_response — exitCode != 0（异步版 hook 阻断）
3. attachment.hook_blocking_error — 全部（本身就是阻断错误，PreToolUse 失败）
4. attachment.hook_non_blocking_error — 全部（本身就是非阻断错误，PostToolUse 失败）

触发条件（除 subtype 区分外）：
- 命令含 "gate" 或 "pre"（更宽松，避免漏判）
- 提取 command 时兼容 hook_blocking_error 的嵌套结构（blockingError.command）

输出：GateEvent 列表。
二轮扫描：标记每个 gate 事件之后是否出现 ai_tool_call（retry_seen_after）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from src.models import ClassifiedEntry, DetectorContext, GateEvent
from .base import Detector, register


_GATE_SCRIPT_RE = re.compile(r"\[([a-z0-9\-]+)\]")
_PHASE_IN_CMD_RE = re.compile(r"phase(\d+)", re.IGNORECASE)


@register("gate")
class GateDetector(Detector):
    """*-gate.mjs 拒答检测（4 种 hook subtype）。"""

    def run(
        self,
        entries: List[ClassifiedEntry],
        ctx: DetectorContext,
    ) -> List[Dict[str, Any]]:
        gates: List[GateEvent] = []

        for e in entries:
            should_emit, exit_code, cmd = self._should_emit_gate(e)
            if not should_emit:
                continue
            if not cmd:
                continue

            cmd_lower = cmd.lower()
            # 仅匹配 gate / pre-* 形式的 hook 命令
            if "gate" not in cmd_lower and "pre" not in cmd_lower:
                continue

            att = e.raw.get("attachment", {}) or {}
            stderr = att.get("stderr", "") or ""
            stdout = att.get("stdout", "") or ""
            stop_reason = self._parse_stop_reason(stdout)

            # script 名：优先从 stderr 的 [script-name] 前缀提取；
            # 否则用 command 空格转连字符（如 'phase0 pre-init workdir' → 'phase0-pre-init-workdir'）。
            script = cmd
            m = _GATE_SCRIPT_RE.search(stderr)
            if m:
                script = m.group(1)
            else:
                script = cmd.replace(" ", "-")

            gates.append(
                GateEvent(
                    kind="gate_rejected",
                    gate_script=script,
                    phase=_phase_from(cmd),
                    blocked_skill=None,
                    exit_code=exit_code,
                    stop_reason=stop_reason,
                    evidence_ref=e.uuid() or "",
                    at=e.timestamp(),
                    retry_seen_after=False,
                )
            )

        # 二轮扫描：标记 retry_seen_after
        gate_uuids = {g.evidence_ref for g in gates}
        if gates:
            for e in entries:
                if e.entry_class != "ai_tool_call":
                    continue
                for g in gates:
                    if g.evidence_ref in gate_uuids and e.timestamp() > g.at and not g.retry_seen_after:
                        g.retry_seen_after = True

        return [g.to_dict() for g in gates]

    @staticmethod
    def _should_emit_gate(e: ClassifiedEntry) -> "tuple[bool, int, str]":
        """判断是否触发 gate_rejected + 提取 exitCode + 提取 command。

        返回 (should_emit, exit_code, command)。
        """
        cls = e.entry_class
        att = e.raw.get("attachment", {}) or {}

        if cls == "attachment.hook_success":
            exit_code = att.get("exitCode", 0)
            if exit_code == 0:
                return False, 0, ""
            return True, exit_code, (att.get("command", "") or "").strip()

        if cls == "attachment.async_hook_response":
            exit_code = att.get("exitCode", 0)
            if exit_code == 0:
                return False, 0, ""
            return True, exit_code, (att.get("command", "") or "").strip()

        if cls == "attachment.hook_blocking_error":
            # blocking_error 本身就是错误，exitCode 默认 0 用 1 兜底
            exit_code = att.get("exitCode", 0) or 1
            # command 可能在嵌套 blockingError.command 里
            cmd = att.get("command", "")
            if not cmd:
                blocking_error = att.get("blockingError", {}) or {}
                cmd = blocking_error.get("command", "") if isinstance(blocking_error, dict) else ""
            return True, exit_code, (cmd or "").strip()

        if cls == "attachment.hook_non_blocking_error":
            exit_code = att.get("exitCode", 0) or 1
            return True, exit_code, (att.get("command", "") or "").strip()

        return False, 0, ""

    @staticmethod
    def _parse_stop_reason(stdout: str) -> str:
        """stdout 通常是 `{"continue": false, "stopReason": "..."}`；解析失败返空。"""
        if not stdout:
            return ""
        try:
            obj = json.loads(stdout)
        except (ValueError, TypeError):
            return ""
        if isinstance(obj, dict):
            return str(obj.get("stopReason", "") or "")
        return ""


def _phase_from(cmd: str) -> Optional[str]:
    m = _PHASE_IN_CMD_RE.search(cmd)
    return f"phase{m.group(1)}" if m else None