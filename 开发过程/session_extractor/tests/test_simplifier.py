"""
测试简化器（v3）

覆盖：
- entry_class 强制保留
- 整类型 DROP（config 缺块）→ 返回 None
- attachment 整类型 DROP：todo_reminder / skill_listing
- attachment.hook_success 保留
- 不保留 message.model / message.usage
- 不保留 message.content[*].type
- 保留 message.content[*].tool_use_id / is_error / text / content
- truncation 默认 OFF；config truncate_enabled=true 才截断
- _get_path / _set_path / _strip_wildcard 工具函数
"""

import unittest
import sys
import os
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.simplifier import (
    simplify_entry,
    simplify_entries,
    load_config,
    _get_path,
    _set_path,
    _strip_wildcard,
    _iter_path_steps,
    _truncate_str,
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "entry_fields_config.json")


def make_config(overrides=None):
    """读 config 并允许单测中覆盖（不持久化）。"""
    cfg = load_config(CONFIG_PATH)
    if overrides:
        for k, v in overrides.items():
            cfg[k] = v
    return cfg


class TestPathHelpers(unittest.TestCase):
    def test_iter_path_steps(self):
        self.assertEqual(
            _iter_path_steps("message.content[*].text"),
            [("message", None, False), ("content", None, True), ("text", None, False)],
        )
        self.assertEqual(_iter_path_steps("uuid"), [("uuid", None, False)])

    def test_get_path_simple(self):
        e = {"a": {"b": {"c": "x"}}}
        self.assertEqual(_get_path(e, "a.b.c"), ["x"])
        self.assertEqual(_get_path(e, "a.b"), [{"c": "x"}])
        self.assertEqual(_get_path(e, "missing"), [])

    def test_get_path_wildcard(self):
        e = {"items": [{"v": 1}, {"v": 2}, {"v": 3}]}
        self.assertEqual(_get_path(e, "items[*].v"), [1, 2, 3])

    def test_strip_wildcard(self):
        self.assertEqual(_strip_wildcard("message.content[*].text"), "message.content")
        self.assertEqual(_strip_wildcard("attachment.content[*]"), "attachment.content")

    def test_set_path_creates_intermediate(self):
        sim = {}
        _set_path(sim, "a.b.c", 1)
        self.assertEqual(sim, {"a": {"b": {"c": 1}}})


class TestSimplifierV3(unittest.TestCase):
    """v3 行为"""

    def test_user_command_keeps_message(self):
        """v3.1：user_command 保留 message（含 caveat 命令内容）。"""
        e = {
            "uuid": "u1", "parentUuid": None, "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "user", "entry_class": "user_command",
            "message": {"content": "<local-command-caveat>caveat</local-command-caveat>"},
            "promptId": "p1", "sessionId": "s1",
        }
        out = simplify_entry(e, make_config())
        self.assertIsNotNone(out)
        self.assertEqual(out["entry_class"], "user_command")
        self.assertIn("message", out)
        self.assertEqual(out["message"]["content"], "<local-command-caveat>caveat</local-command-caveat>")
        self.assertNotIn("promptId", out)
        self.assertNotIn("sessionId", out)

    def test_type_field_dropped_globally(self):
        """v3.1：所有 entry_class 输出都不应有 type 字段（entry_class 足够）。"""
        e = {
            "uuid": "a1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "assistant", "entry_class": "ai_text",
            "message": {
                "content": [{"type": "text", "text": "hi"}],
                "stop_reason": "end_turn", "stop_sequence": None,
            },
        }
        out = simplify_entry(e, make_config())
        self.assertNotIn("type", out)

    def test_user_input_keeps_message_content(self):
        e = {
            "uuid": "u1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "user", "entry_class": "user_input",
            "message": {"content": [{"type": "text", "text": "hello"}]},
        }
        out = simplify_entry(e, make_config())
        self.assertEqual(out["message"]["content"], [{"text": "hello"}])
        self.assertNotIn("type", out["message"]["content"][0])

    def test_tool_result_keeps_link_fields(self):
        e = {
            "uuid": "u1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "user", "entry_class": "tool_result",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_123", "is_error": False, "content": "body"}
                ]
            },
            "sourceToolAssistantUUID": "asst-uuid",
            "toolUseResult": {"stdout": "body", "stderr": ""},
        }
        out = simplify_entry(e, make_config())
        self.assertIn("sourceToolAssistantUUID", out)
        self.assertIn("toolUseResult", out)
        self.assertEqual(out["toolUseResult"]["stdout"], "body")
        item = out["message"]["content"][0]
        self.assertEqual(item["tool_use_id"], "call_123")
        self.assertEqual(item["is_error"], False)
        self.assertEqual(item["content"], "body")
        self.assertNotIn("type", item)

    def test_ai_text_keeps_text_and_stop(self):
        e = {
            "uuid": "a1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "assistant", "entry_class": "ai_text",
            "message": {
                "content": [{"type": "text", "text": "hi"}],
                "model": "m", "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        }
        out = simplify_entry(e, make_config())
        self.assertEqual(out["message"]["content"][0]["text"], "hi")
        self.assertNotIn("type", out["message"]["content"][0])
        self.assertEqual(out["message"]["stop_reason"], "end_turn")
        self.assertIn("stop_sequence", out["message"])
        self.assertNotIn("model", out["message"])
        self.assertNotIn("usage", out["message"])

    def test_ai_tool_call_keeps_name_input_id(self):
        e = {
            "uuid": "a1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "assistant", "entry_class": "ai_tool_call",
            "message": {
                "content": [{"type": "tool_use", "id": "call_1", "name": "Bash", "input": {"command": "ls"}}],
                "model": "m", "stop_reason": "tool_use", "stop_sequence": None,
            },
        }
        out = simplify_entry(e, make_config())
        item = out["message"]["content"][0]
        self.assertEqual(item["name"], "Bash")
        self.assertEqual(item["input"], {"command": "ls"})
        self.assertEqual(item["id"], "call_1")
        self.assertNotIn("type", item)
        self.assertNotIn("model", out["message"])

    def test_attachment_hook_success_kept(self):
        e = {
            "uuid": "a1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "attachment", "entry_class": "attachment",
            "attachment": {
                "type": "hook_success",
                "hookName": "Stop", "hookEvent": "Stop", "command": "phase4",
                "exitCode": 0, "durationMs": 72,
            },
        }
        out = simplify_entry(e, make_config())
        self.assertIsNotNone(out)
        self.assertEqual(out["entry_class"], "attachment.hook_success")
        self.assertEqual(out["attachment"]["hookName"], "Stop")
        self.assertEqual(out["attachment"]["exitCode"], 0)

    def test_attachment_todo_reminder_whole_type_drop(self):
        e = {
            "uuid": "a1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "attachment", "entry_class": "attachment",
            "attachment": {"type": "todo_reminder", "content": ["todo1"]},
        }
        out = simplify_entry(e, make_config())
        self.assertIsNone(out)

    def test_attachment_skill_listing_whole_type_drop(self):
        e = {
            "uuid": "a1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "attachment", "entry_class": "attachment",
            "attachment": {"type": "skill_listing", "content": "list"},
        }
        out = simplify_entry(e, make_config())
        self.assertIsNone(out)

    def test_whole_type_drop_no_config_block(self):
        e = {
            "uuid": "x", "parentUuid": None, "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "queue-operation", "entry_class": "queue-operation",
            "operation": "enqueue",
        }
        out = simplify_entry(e, make_config())
        self.assertIsNone(out)

    def test_whole_type_drop_for_5_types(self):
        cfg = make_config()
        for cls in ["queue-operation", "file-history-snapshot", "last-prompt", "system", "permission-mode"]:
            e = {
                "uuid": "x", "parentUuid": None, "timestamp": "2026-01-01T00:00:00.000Z",
                "type": cls, "entry_class": cls,
            }
            self.assertIsNone(simplify_entry(e, cfg), f"{cls} should be whole-type drop")

    def test_truncate_disabled_by_default(self):
        e = {
            "uuid": "a1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "assistant", "entry_class": "ai_text",
            "message": {
                "content": [{"type": "text", "text": "a" * 10000}],
                "stop_reason": "end_turn", "stop_sequence": None,
            },
        }
        out = simplify_entry(e, make_config())
        self.assertEqual(len(out["message"]["content"][0]["text"]), 10000)

    def test_truncate_enabled_truncates_long_text(self):
        cfg = make_config({"truncate_enabled": True})
        e = {
            "uuid": "a1", "parentUuid": "p", "timestamp": "2026-01-01T00:00:00.000Z",
            "type": "assistant", "entry_class": "ai_text",
            "message": {
                "content": [{"type": "text", "text": "a" * 10000}],
                "stop_reason": "end_turn", "stop_sequence": None,
            },
        }
        out = simplify_entry(e, cfg)
        self.assertLess(len(out["message"]["content"][0]["text"]), 10000)
        self.assertIn("truncated", out["message"]["content"][0]["text"])

    def test_cwd_change_entry_kept(self):
        e = {
            "type": "cwd_change", "entry_class": "cwd_change",
            "uuid": "new", "timestamp": "2026-01-01T00:00:00.000Z",
            "cwd": "/new", "prevCwd": "/old",
        }
        out = simplify_entry(e, make_config())
        self.assertIsNotNone(out)
        self.assertEqual(out["cwd"], "/new")
        self.assertEqual(out["prevCwd"], "/old")

    def test_simplify_entries_filters_dropped(self):
        cfg = make_config()
        entries = [
            {"uuid": "1", "parentUuid": None, "timestamp": "2026-01-01T00:00:00.000Z", "type": "queue-operation", "entry_class": "queue-operation"},
            {"uuid": "2", "parentUuid": None, "timestamp": "2026-01-01T00:00:01.000Z", "type": "last-prompt", "entry_class": "last-prompt", "lastPrompt": "x"},
            {"uuid": "3", "parentUuid": None, "timestamp": "2026-01-01T00:00:02.000Z", "type": "user", "entry_class": "user_input", "message": {"content": "hi"}},
        ]
        out = simplify_entries(entries, CONFIG_PATH)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["entry_class"], "user_input")


if __name__ == "__main__":
    unittest.main()