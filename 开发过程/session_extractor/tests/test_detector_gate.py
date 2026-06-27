"""
gate detector 单测。
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.detectors.gate import GateDetector
from src.models import ClassifiedEntry, DetectorContext
from tests._detector_helpers import hook_success, ai_tool_call


class TestGateDetector(unittest.TestCase):
    def setUp(self):
        self.det = GateDetector()
        self.ctx = DetectorContext()

    def test_empty_input(self):
        self.assertEqual(self.det.run([], self.ctx), [])

    def test_exit_code_zero_ignored(self):
        entries = [hook_success("u1", "phase0 pre-init workdir", exit_code=0)]
        self.assertEqual(self.det.run(entries, self.ctx), [])

    def test_rejected_gate_detected(self):
        entries = [
            hook_success(
                "u1", "phase0 pre-init workdir",
                exit_code=2,
                stderr="[phase0-pre-init-workdir] 无法提取需求ID",
                stdout='{"continue": false, "stopReason": "blocked"}',
                hook_name="PreToolUse:Skill",
            ),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        g = out[0]
        self.assertEqual(g["kind"], "gate_rejected")
        self.assertEqual(g["gate_script"], "phase0-pre-init-workdir")
        self.assertEqual(g["phase"], "phase0")
        self.assertEqual(g["exit_code"], 2)
        self.assertEqual(g["stop_reason"], "blocked")
        self.assertFalse(g["retry_seen_after"])

    def test_retry_seen_after_flag(self):
        entries = [
            hook_success("u1", "phase0 pre-init workdir", exit_code=2, hook_name="PreToolUse:Skill"),
            ai_tool_call("u2", timestamp="2026-06-27T00:00:01Z"),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["retry_seen_after"])

    def test_no_retry_after_gate(self):
        entries = [
            hook_success("u1", "phase0 pre-init workdir", exit_code=2, hook_name="PreToolUse:Skill"),
            # 后续只有 ai_text，没有 retry
        ]
        from src.models import ClassifiedEntry
        entries.append(ClassifiedEntry(
            raw={"uuid": "u2", "timestamp": "2026-06-27T00:00:01Z",
                 "message": {"content": [{"type": "text", "text": "ok"}]}},
            entry_class="ai_text",
        ))
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertFalse(out[0]["retry_seen_after"])

    def test_non_gate_command_ignored(self):
        entries = [
            hook_success("u1", "tool post healthcheck", exit_code=2,
                         stderr="some error"),  # 不含 gate/pre
            hook_success("u2", "phase2 post-task-planning", exit_code=2),  # post 而非 pre
        ]
        out = self.det.run(entries, self.ctx)
        # u2 的 command 含 "post" 但不含 "gate" / "pre" — 应被忽略
        self.assertEqual(out, [])

    def test_stop_reason_parse_failure(self):
        entries = [
            hook_success("u1", "phase0 pre-init workdir", exit_code=2,
                         stdout="not json"),  # stdout 不是合法 JSON
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out[0]["stop_reason"], "")

    def test_real_sample_phase0_pre_init(self):
        """1b4c0c37 真实样本 idx 34：PreToolUse:Skill, exitCode=2, command='phase0 pre-init workdir'"""
        entries = [
            hook_success(
                "u1", "phase0 pre-init workdir",
                exit_code=2,
                stderr="[phase0-pre-init-workdir] blocked",
                stdout='{"continue":false}',
                hook_event="PreToolUse",
                hook_name="PreToolUse:Skill",
            ),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["phase"], "phase0")
        self.assertEqual(out[0]["gate_script"], "phase0-pre-init-workdir")


def hook_blocking_error(uuid, command="phase0 pre-init workdir", timestamp="2026-06-27T00:00:00Z"):
    """构造 attachment.hook_blocking_error entry（PreToolUse 失败）。"""
    return ClassifiedEntry(
        raw={
            "uuid": uuid,
            "timestamp": timestamp,
            "attachment": {
                "type": "hook_blocking_error",
                "hookName": "PreToolUse:Bash",
                "hookEvent": "PreToolUse",
                "blockingError": {
                    "blockingError": "[Fact-Forcing Gate] Before the first Bash command...",
                    "command": command,
                },
            },
        },
        entry_class="attachment.hook_blocking_error",
    )


def hook_non_blocking_error(uuid, command="phase0 post-init phase_status", timestamp="2026-06-27T00:00:00Z"):
    """构造 attachment.hook_non_blocking_error entry（PostToolUse 失败）。"""
    return ClassifiedEntry(
        raw={
            "uuid": uuid,
            "timestamp": timestamp,
            "attachment": {
                "type": "hook_non_blocking_error",
                "hookName": "PostToolUse:Skill",
                "hookEvent": "PostToolUse",
                "stderr": "Failed with non-blocking status code: ENOENT...",
                "stdout": "",
                "exitCode": 1,
                "command": command,
                "durationMs": 201,
            },
        },
        entry_class="attachment.hook_non_blocking_error",
    )


def async_hook_response(uuid, exit_code=0, command="", timestamp="2026-06-27T00:00:00Z"):
    """构造 attachment.async_hook_response entry。"""
    return ClassifiedEntry(
        raw={
            "uuid": uuid,
            "timestamp": timestamp,
            "attachment": {
                "type": "async_hook_response",
                "processId": "async_hook_140465",
                "hookName": "PreToolUse:Skill",
                "hookEvent": "PreToolUse",
                "response": {"tool_use_id": "call_xxx"},
                "stdout": "{}",
                "stderr": "",
                "exitCode": exit_code,
                "command": command,
            },
        },
        entry_class="attachment.async_hook_response",
    )


class TestGateDetectorExtendedSubtypes(unittest.TestCase):
    """4 种 hook subtype 都应触发 gate detector。"""

    def setUp(self):
        self.det = GateDetector()
        self.ctx = DetectorContext()

    def test_hook_blocking_error_emits(self):
        """hook_blocking_error 全部触发（本身就是错误，exitCode 默认 0 兜底为 1）。"""
        entries = [hook_blocking_error("u1")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "gate_rejected")
        self.assertEqual(out[0]["gate_script"], "phase0-pre-init-workdir")
        self.assertEqual(out[0]["phase"], "phase0")
        self.assertEqual(out[0]["exit_code"], 1)

    def test_hook_blocking_error_non_gate_skipped(self):
        """hook_blocking_error 但 command 不含 gate/pre → 跳过。"""
        entries = [hook_blocking_error("u1", command="phase4 unrelated-hook")]   # 改用 gate 防误解
        # 实际上命令改为非门控型
        entries[0].raw["attachment"]["blockingError"]["command"] = "phase4 summarize"
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out, [])

    def test_hook_non_blocking_error_emits(self):
        """hook_non_blocking_error 全部触发，exitCode 取 attachment 的。"""
        entries = [hook_non_blocking_error("u1", command="phase0 pre-init workdir")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gate_script"], "phase0-pre-init-workdir")
        self.assertEqual(out[0]["phase"], "phase0")
        self.assertEqual(out[0]["exit_code"], 1)

    def test_async_hook_response_exit_nonzero_emits(self):
        """async_hook_response exitCode != 0 触发（异步版 hook 阻断）。"""
        entries = [async_hook_response("u1", exit_code=2, command="phase0 pre-init workdir")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gate_script"], "phase0-pre-init-workdir")
        self.assertEqual(out[0]["exit_code"], 2)

    def test_async_hook_response_exit_zero_skipped(self):
        """async_hook_response exitCode=0 跳过（成功不算 gate 拒答）。"""
        entries = [async_hook_response("u1", exit_code=0, command="phase0 pre-init workdir")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out, [])

    def test_hook_blocking_error_without_command_in_nested(self):
        """hook_blocking_error 没有 blockingError.command → 跳过（无法判定阶段）。"""
        from src.models import ClassifiedEntry
        entries = [ClassifiedEntry(
            raw={
                "uuid": "u1", "timestamp": "2026-06-27T00:00:00Z",
                "attachment": {"type": "hook_blocking_error", "hookName": "PreToolUse"},
            },
            entry_class="attachment.hook_blocking_error",
        )]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()