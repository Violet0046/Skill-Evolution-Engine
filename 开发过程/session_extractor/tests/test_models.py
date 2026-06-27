"""
src/models.py 单测 — 验证 dataclass + to_dict() 正确性。
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import (
    ClassifiedEntry,
    DetectorContext,
    EvidenceBundle,
    PhaseTransition,
    GateEvent,
    ReviewContractEvent,
    UserConfirmationEvent,
    SymlinkHopEvent,
)


class TestClassifiedEntry(unittest.TestCase):
    def test_uuid_and_timestamp_helpers(self):
        e = ClassifiedEntry(
            raw={"uuid": "abc", "timestamp": "2026-06-27T00:00:00Z"},
            entry_class="ai_text",
        )
        self.assertEqual(e.uuid(), "abc")
        self.assertEqual(e.timestamp(), "2026-06-27T00:00:00Z")

    def test_uuid_returns_none_when_absent(self):
        e = ClassifiedEntry(raw={}, entry_class="user_input")
        self.assertIsNone(e.uuid())
        self.assertEqual(e.timestamp(), "")


class TestDetectorContext(unittest.TestCase):
    def test_defaults(self):
        ctx = DetectorContext()
        self.assertEqual(ctx.spec, {})
        self.assertEqual(ctx.env, {})
        self.assertEqual(ctx.cwd_realpath_cache, {})

    def test_with_values(self):
        ctx = DetectorContext(
            spec={"name": "requirement_analysis"},
            env={"AUTO_CONFIRM": "1"},
            cwd_realpath_cache={"/a": "/b"},
        )
        self.assertEqual(ctx.spec["name"], "requirement_analysis")
        self.assertEqual(ctx.env["AUTO_CONFIRM"], "1")
        self.assertEqual(ctx.cwd_realpath_cache["/a"], "/b")


class TestEvidenceBundle(unittest.TestCase):
    def test_to_dict_round_trip(self):
        bundle = EvidenceBundle(
            schema_version="4.0",
            session={"sessionId": "x"},
            cwd_changes=2,
            trace=[{"entry_class": "ai_text", "uuid": "a"}],
            state_machine={"phases": ["phase1"], "transitions": [], "unexpected_exits": []},
            constraint_events=[{"kind": "gate_rejected", "evidence_ref": "a"}],
            user_feedback=[],
            execution_pattern={"step_counts": {"ai_text": 1}},
            detector_meta={"enabled": ["state_machine"], "truncate_enabled": True},
        )
        d = bundle.to_dict()
        self.assertEqual(d["schema_version"], "4.0")
        self.assertEqual(d["cwd_changes"], 2)
        self.assertEqual(d["state_machine"]["phases"], ["phase1"])
        self.assertEqual(len(d["constraint_events"]), 1)
        self.assertEqual(d["detector_meta"]["truncate_enabled"], True)


class TestDetectorEventDataclasses(unittest.TestCase):
    def test_phase_transition(self):
        e = PhaseTransition(
            phase="phase0",
            hook_event="PreToolUse",
            trigger_entry_uuid="u1",
            trigger_attachment_command="phase0 pre-init workdir",
            trigger_hook_name="PreToolUse:Skill",
            at="2026-06-27T00:00:00Z",
            role="pre-init workdir",
        )
        d = e.to_dict()
        self.assertEqual(d["phase"], "phase0")
        self.assertEqual(d["role"], "pre-init workdir")

    def test_gate_event(self):
        e = GateEvent(
            kind="gate_rejected",
            gate_script="phase0-pre-init-workdir",
            phase="phase0",
            blocked_skill=None,
            exit_code=2,
            stop_reason="无法提取需求ID",
            evidence_ref="u1",
            at="2026-06-27T00:00:00Z",
            retry_seen_after=True,
        )
        d = e.to_dict()
        self.assertEqual(d["kind"], "gate_rejected")
        self.assertEqual(d["exit_code"], 2)
        self.assertTrue(d["retry_seen_after"])

    def test_review_contract_event(self):
        e = ReviewContractEvent(
            kind="review_contract",
            issue="missing_passed_field",
            reviewer_subagent_type="review-agent",
            expected_subagent_types=["review-agent"],
            actual_subagent_type="review-agent",
            retry_count=2,
            evidence_ref="u1",
            at="2026-06-27T00:00:00Z",
        )
        d = e.to_dict()
        self.assertEqual(d["issue"], "missing_passed_field")
        self.assertEqual(d["retry_count"], 2)

    def test_user_confirmation_event(self):
        e = UserConfirmationEvent(
            kind="user_confirmation",
            mode="auto_confirm",
            trigger="[auto-confirm]",
            evidence_ref="u1",
            at="2026-06-27T00:00:00Z",
            auto_confirm_env="1",
        )
        d = e.to_dict()
        self.assertEqual(d["mode"], "auto_confirm")
        self.assertEqual(d["auto_confirm_env"], "1")

    def test_symlink_hop_event(self):
        e = SymlinkHopEvent(
            kind="symlink_hop",
            logical_cwd="/link/path",
            physical_cwd="/real/path",
            evidence_ref="u1",
            at="2026-06-27T00:00:00Z",
        )
        d = e.to_dict()
        self.assertEqual(d["logical_cwd"], "/link/path")
        self.assertEqual(d["physical_cwd"], "/real/path")


if __name__ == "__main__":
    unittest.main()