"""
review_contract detector 单测。
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.detectors.review_contract import ReviewContractDetector
from src.models import ClassifiedEntry, DetectorContext


def ai_agent_call(uuid, subagent_type, tool_use_id=None, timestamp="2026-06-27T00:00:00Z"):
    return ClassifiedEntry(
        raw={
            "uuid": uuid,
            "timestamp": timestamp,
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": tool_use_id or uuid,
                    "name": "Agent",
                    "input": {"subagent_type": subagent_type},
                }],
            },
        },
        entry_class="ai_tool_call",
    )


def tool_result(uuid, tool_use_id, tool_use_result, timestamp="2026-06-27T00:00:01Z"):
    return ClassifiedEntry(
        raw={
            "uuid": uuid,
            "timestamp": timestamp,
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": ""}],
            },
            "toolUseResult": tool_use_result,
        },
        entry_class="tool_result",
    )


class TestReviewContractDetector(unittest.TestCase):
    def setUp(self):
        self.det = ReviewContractDetector()
        self.ctx = DetectorContext()

    def test_empty_input(self):
        self.assertEqual(self.det.run([], self.ctx), [])

    def test_no_review_agent_no_events(self):
        entries = [
            ai_agent_call("u1", subagent_type="general-purpose"),
        ]
        self.assertEqual(self.det.run(entries, self.ctx), [])

    def test_review_agent_called_without_spec_is_clean(self):
        """spec 缺省时只检测存在性，不报错。"""
        entries = [
            ai_agent_call("u1", subagent_type="review-agent", tool_use_id="call1"),
            tool_result("u2", "call1", {"passed": True}),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(out, [])

    def test_missing_passed_field_detected(self):
        """spec 含 required_fields + retry_count 时，缺 passed 报警。"""
        entries = [
            ai_agent_call("u1", subagent_type="review-agent", tool_use_id="call1"),
            tool_result("u2", "call1", {"retryAdvice": "do it again"}),
        ]
        ctx = DetectorContext(spec={
            "subagents": {
                "review-agent": {
                    "expected_subagent_types": ["review-agent"],
                    "required_fields": ["passed", "retryAdvice"],
                    "retry_count": 2,
                }
            }
        })
        out = self.det.run(entries, ctx)
        # missing 'passed'
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["issue"], "missing_required_field")
        self.assertEqual(out[0]["reviewer_subagent_type"], "review-agent")

    def test_subagent_type_mismatch_detected(self):
        entries = [
            ai_agent_call("u1", subagent_type="wrong-review-agent", tool_use_id="call1"),
        ]
        ctx = DetectorContext(spec={
            "subagents": {
                "review-agent": {"expected_subagent_types": ["review-agent"]}
            }
        })
        out = self.det.run(entries, ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["issue"], "subagent_type_mismatch")

    def test_retry_exceeded_detected(self):
        entries = [
            ai_agent_call("u1", subagent_type="review-agent", tool_use_id="call1"),
            tool_result("u2", "call1", {"passed": False, "retryAdvice": "x", "retryCount": 5}),
        ]
        ctx = DetectorContext(spec={
            "subagents": {
                "review-agent": {
                    "expected_subagent_types": ["review-agent"],
                    "required_fields": ["passed", "retryAdvice"],
                    "retry_count": 2,
                }
            }
        })
        out = self.det.run(entries, ctx)
        issues = {e["issue"] for e in out}
        self.assertIn("retry_exceeded", issues)

    def test_review_summary_agent_substring_match(self):
        """spec 缺省时，"review-summary-agent" 也会被匹配（子串包含 'review'）。"""
        entries = [
            ai_agent_call("u1", subagent_type="review-summary-agent", tool_use_id="call1"),
        ]
        out = self.det.run(entries, self.ctx)
        # spec 缺省 + 通过存在性检测 + passed 字段不存在 → missing_required_field
        # 但因为 spec 缺省，没有 required_fields 限制，所以无报警
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()