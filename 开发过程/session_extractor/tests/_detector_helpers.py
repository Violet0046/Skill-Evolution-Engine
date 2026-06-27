"""
detector 测试共享 fixture — 把 hook_success / ai_text / ai_tool_call / user_input
4 个 ClassifiedEntry 构造器抽出来，5 个 test_detector_*.py 顶部改用共享 import。

净减约 60 行重复代码。

每个 helper 的第一个位置参数是 uuid（兼容原测试"位置传 uuid"的用法），
未传时自动生成。
"""

import sys
import os
import uuid as uuid_lib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import ClassifiedEntry


def _uuid_or_new(uuid: "str | None") -> str:
    return uuid if uuid else str(uuid_lib.uuid4())


def hook_success(
    uuid: "str | None" = None,
    command: str = "phase0 pre-init workdir",
    exit_code: int = 0,
    stderr: str = "",
    stdout: str = "",
    hook_event: str = "PreToolUse",
    hook_name: str = "PreToolUse:Skill",
    timestamp: str = "2026-06-27T00:00:00Z",
) -> ClassifiedEntry:
    """构造 attachment.hook_success entry。"""
    return ClassifiedEntry(
        raw={
            "uuid": _uuid_or_new(uuid),
            "timestamp": timestamp,
            "attachment": {
                "type": "hook_success",
                "command": command,
                "hookEvent": hook_event,
                "hookName": hook_name,
                "exitCode": exit_code,
                "stderr": stderr,
                "stdout": stdout,
                "durationMs": 10,
            },
        },
        entry_class="attachment.hook_success",
    )


def ai_text(
    uuid: "str | None" = None,
    text: str = "hello",
    timestamp: str = "2026-06-27T00:00:01Z",
) -> ClassifiedEntry:
    """构造 ai_text entry。"""
    return ClassifiedEntry(
        raw={
            "uuid": _uuid_or_new(uuid),
            "timestamp": timestamp,
            "message": {"content": [{"type": "text", "text": text}]},
        },
        entry_class="ai_text",
    )


def ai_tool_call(
    uuid: "str | None" = None,
    name: str = "Skill",
    timestamp: str = "2026-06-27T00:00:01Z",
) -> ClassifiedEntry:
    """构造 ai_tool_call entry（默认 Skill 工具）。"""
    u = _uuid_or_new(uuid)
    return ClassifiedEntry(
        raw={
            "uuid": u,
            "timestamp": timestamp,
            "message": {
                "content": [{"type": "tool_use", "id": u, "name": name, "input": {}}],
            },
        },
        entry_class="ai_tool_call",
    )


def user_input(
    uuid: "str | None" = None,
    text: str = "",
    permission_mode: "str | None" = None,
    timestamp: str = "2026-06-27T00:00:00Z",
) -> ClassifiedEntry:
    """构造 user_input entry。"""
    raw = {
        "uuid": _uuid_or_new(uuid),
        "timestamp": timestamp,
        "message": {"content": [{"type": "text", "text": text}]},
    }
    if permission_mode:
        raw["permissionMode"] = permission_mode
    return ClassifiedEntry(raw=raw, entry_class="user_input")