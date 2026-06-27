"""
state_machine detector 单测。
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.detectors.state_machine import StateMachineDetector
from src.models import ClassifiedEntry, DetectorContext
from tests._detector_helpers import hook_success, ai_text


class TestStateMachineDetector(unittest.TestCase):
    def setUp(self):
        self.det = StateMachineDetector()
        self.ctx = DetectorContext()

    def test_empty_input(self):
        out = self.det.run([], self.ctx)
        self.assertEqual(out, [{
            "kind": "state_machine",
            "phases": [],
            "transitions": [],
            "unexpected_exits": [],
        }])

    def test_single_phase_recognized(self):
        entries = [hook_success("u1", "phase0 pre-init workdir")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out[0]["phases"], ["phase0"])
        self.assertEqual(len(out[0]["transitions"]), 1)
        t = out[0]["transitions"][0]
        self.assertEqual(t["phase"], "phase0")
        self.assertEqual(t["role"], "pre-init workdir")
        self.assertEqual(t["hook_event"], "PreToolUse")

    def test_multiple_phases_preserve_order(self):
        entries = [
            hook_success("u1", "phase0 pre-init workdir"),
            ai_text("u2"),
            hook_success("u3", "phase2 pre-subagent", hook_event="PreToolUse"),
            hook_success("u4", "phase3 post-subagent-review", hook_event="PostToolUse"),
            hook_success("u5", "phase4 post-summary", hook_event="Stop"),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out[0]["phases"], ["phase0", "phase2", "phase3", "phase4"])
        self.assertEqual(len(out[0]["transitions"]), 4)

    def test_unknown_command_ignored(self):
        entries = [
            hook_success("u1", "tool post healthcheck"),
            hook_success("u2", "phase1 pre-init workdir"),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out[0]["phases"], ["phase1"])
        self.assertEqual(len(out[0]["transitions"]), 1)

    def test_phase_jump_triggers_unexpected_exit(self):
        # phase0 → phase2 跳跃：phase0 那条被标记为 unexpected_exit
        entries = [
            hook_success("u1", "phase0 pre-init workdir"),
            hook_success("u2", "phase2 pre-subagent", hook_event="PreToolUse"),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out[0]["unexpected_exits"]), 1)
        self.assertEqual(out[0]["unexpected_exits"][0]["phase"], "phase0")

    def test_ai_text_ignored(self):
        entries = [ai_text("u1", text="not a hook")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out[0]["phases"], [])

    def test_spec_overrides_phase_regex(self):
        # spec.phases 限制只识别 phase1 / phase3（缺省会识别全部）
        entries = [
            hook_success("u1", "phase0 pre-init workdir"),
            hook_success("u2", "phase1 pre-init workdir"),
            hook_success("u3", "phase3 post-subagent-review"),
        ]
        ctx = DetectorContext(spec={"phases": [{"name": "phase1"}, {"name": "phase3"}]})
        out = self.det.run(entries, ctx)
        self.assertEqual(out[0]["phases"], ["phase1", "phase3"])
        self.assertEqual(len(out[0]["transitions"]), 2)

    def test_real_sample_command_values_match(self):
        """真实样本 1b4c0c37 中的 phase 命令值应当被识别。"""
        entries = [
            hook_success("u1", "phase0 pre-init workdir", hook_name="PreToolUse:Skill"),
            hook_success("u2", "phase4 post-summary", hook_event="Stop", hook_name="Stop"),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out[0]["phases"], ["phase0", "phase4"])
        self.assertEqual(out[0]["transitions"][0]["trigger_hook_name"], "PreToolUse:Skill")
        self.assertEqual(out[0]["transitions"][1]["trigger_hook_name"], "Stop")


if __name__ == "__main__":
    unittest.main()