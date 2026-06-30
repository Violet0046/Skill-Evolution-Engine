"""
v4 collector 端到端测试 — 三层 e2e 合并：

- TestE2EFakeSession：伪样本（默认跑）— 原 test_pipeline.py 的 5 个测试
- TestE2ERealSession：真实样本（RUN_REAL=1）— 原 test_pipeline_real.py 的 1 个 + test_integration.py 的 test_with_real_session
- TestE2EIntegration：v3 集成流程（默认跑）— 原 test_integration.py 的 test_full_pipeline

test_v3_compat.py 单独保留为最硬契约测试，永不合并。
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline import run as pipeline_run
from 开发过程.session_extractor.src.simplify.classifier import classify_entry
from src.util.session_io import load_session_entries
from src.util.timestamp import parse_timestamp, sort_by_timestamp


# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

CONFIG_PATH = str(Path(__file__).parent.parent / "src" / "simplify" / "entry_fields_config.json")
SPECS_DIR = str(Path(__file__).parent.parent / "specs")
REAL_SESSION = str(
    Path(__file__).parent.parent / "1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl"
)


# ---------------------------------------------------------------------------
# 伪样本构造
# ---------------------------------------------------------------------------


def fake_session_entries():
    """构造一条模拟需求分析 agent 的 session，覆盖 5 类 detector 信号。"""
    return [
        # user 输入
        {"uuid": "u1", "parentUuid": None, "timestamp": "2026-06-27T01:00:00Z",
         "type": "user", "message": {"content": [{"type": "text", "text": "请分析 RAN-1234"}]},
         "sessionId": "test", "version": "2.1", "cwd": "/work"},

        # phase0 pre-init workdir 拒答（exitCode=2）
        {"uuid": "u2", "parentUuid": "u1", "timestamp": "2026-06-27T01:00:01Z",
         "type": "attachment", "attachment": {
             "type": "hook_success", "command": "phase0 pre-init workdir",
             "hookEvent": "PreToolUse", "hookName": "PreToolUse:Skill",
             "exitCode": 2, "durationMs": 50,
             "stderr": "[phase0-pre-init-workdir] 无法提取需求ID",
             "stdout": '{"continue": false, "stopReason": "blocked"}',
         }, "cwd": "/work"},

        # retry（ai_tool_call after gate）
        {"uuid": "u3", "parentUuid": "u2", "timestamp": "2026-06-27T01:00:02Z",
         "type": "assistant", "message": {
             "content": [{"type": "tool_use", "id": "call-1", "name": "Skill", "input": {"skill": "查询需求信息"}}]
         }, "cwd": "/work"},

        # user 中断 + 重新输入
        {"uuid": "u4", "parentUuid": "u3", "timestamp": "2026-06-27T01:00:03Z",
         "type": "user", "message": {"content": [{"type": "text", "text": "[Request interrupted by user]"}]},
         "cwd": "/work"},

        # auto-confirm 模式
        {"uuid": "u5", "parentUuid": "u4", "timestamp": "2026-06-27T01:00:04Z",
         "type": "user", "message": {"content": [{"type": "text", "text": "[auto-confirm] continue"}]},
         "cwd": "/work"},

        # phase4 post-summary
        {"uuid": "u6", "parentUuid": "u5", "timestamp": "2026-06-27T01:00:05Z",
         "type": "attachment", "attachment": {
             "type": "hook_success", "command": "phase4 post-summary",
             "hookEvent": "Stop", "hookName": "Stop",
             "exitCode": 0, "durationMs": 72,
             "stdout": '{"continue": true}', "stderr": "",
         }, "cwd": "/work"},

        # review-agent 调用 + 缺 passed 字段
        {"uuid": "u7", "parentUuid": "u6", "timestamp": "2026-06-27T01:00:06Z",
         "type": "assistant", "message": {
             "content": [{"type": "tool_use", "id": "call-review-1",
                          "name": "Agent", "input": {"subagent_type": "review-agent"}}]
         }, "cwd": "/work"},

        # review result（缺 passed 字段）
        {"uuid": "u8", "parentUuid": "u7", "timestamp": "2026-06-27T01:00:07Z",
         "type": "user", "message": {
             "content": [{"type": "tool_result", "tool_use_id": "call-review-1",
                          "content": "", "is_error": False}]
         },
         "toolUseResult": {"retryAdvice": "redo"}, "cwd": "/work"},

        # 整类型 DROP 样本（应被丢弃）
        {"uuid": "u9", "parentUuid": "u8", "timestamp": "2026-06-27T01:00:08Z",
         "type": "queue-operation", "content": "enqueue", "cwd": "/work"},

        # cwd 跳变（应自动给该 entry 标 prev_cwd=/work）
        {"uuid": "u10", "parentUuid": "u8", "timestamp": "2026-06-27T01:00:09Z",
         "type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]},
         "cwd": "/work/sub"},

        # ai_text with <think>（trigger truncation）
        {"uuid": "u11", "parentUuid": "u10", "timestamp": "2026-06-27T01:00:10Z",
         "type": "assistant", "message": {
             "content": [{"type": "text", "text": "<think>" + "x" * 10000 + "</think> final"}],
             "stop_reason": "end_turn", "stop_sequence": None,
         }, "cwd": "/work/sub"},
    ]


def write_fake_session(path):
    entries = fake_session_entries()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False)
    return entries


# ---------------------------------------------------------------------------
# 第一层：伪样本 e2e（默认跑）
# ---------------------------------------------------------------------------


class TestE2EFakeSession(unittest.TestCase):
    """伪样本端到端测试 — 覆盖 5 类 detector 命中 + truncate 默认 ON。"""

    def test_empty_input(self):
        with tempfile.TemporaryDirectory() as d:
            input_path = os.path.join(d, "in.json")
            output_path = os.path.join(d, "out.jsonl")
            with open(input_path, "w", encoding="utf-8") as f:
                f.write("")
            bundle = pipeline_run(input_path, output_path, config_path=CONFIG_PATH, quiet=True)
            self.assertEqual(bundle.schema_version, "4.0")
            self.assertEqual(bundle.cwd_changes, 0)
            self.assertEqual(bundle.state_machine["phases"], [])
            self.assertEqual(bundle.constraint_events, [])

    def test_fake_session_e2e(self):
        with tempfile.TemporaryDirectory() as d:
            input_path = os.path.join(d, "in.json")
            output_path = os.path.join(d, "out.jsonl")
            write_fake_session(input_path)

            bundle = pipeline_run(input_path, output_path, config_path=CONFIG_PATH, quiet=True)

            self.assertEqual(bundle.schema_version, "4.0")
            self.assertEqual(bundle.session["cwd"], "/work")
            self.assertEqual(bundle.session["start_time"], "2026-06-27T01:00:00Z")
            self.assertEqual(bundle.session["end_time"], "2026-06-27T01:00:10Z")
            self.assertEqual(bundle.cwd_changes, 1)

            trace_classes = [e.get("entry_class", "") for e in bundle.trace]
            self.assertNotIn("queue-operation", trace_classes)

            self.assertIn("phase0", bundle.state_machine["phases"])
            self.assertIn("phase4", bundle.state_machine["phases"])
            self.assertEqual(len(bundle.state_machine["transitions"]), 2)

            gate_events = [e for e in bundle.constraint_events if e["kind"] == "gate_rejected"]
            self.assertEqual(len(gate_events), 1)
            self.assertEqual(gate_events[0]["gate_script"], "phase0-pre-init-workdir")
            self.assertEqual(gate_events[0]["exit_code"], 2)
            self.assertTrue(gate_events[0]["retry_seen_after"])

            self.assertEqual(len(bundle.user_feedback), 3)
            self.assertIn("请分析 RAN-1234", bundle.user_feedback[0]["text"])
            self.assertIn("[Request interrupted by user]", bundle.user_feedback[1]["text"])

            self.assertIn("user_input", bundle.execution_pattern["step_counts"])
            self.assertEqual(bundle.detector_meta["truncate_enabled"], True)

            with open(output_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertGreater(len(lines), 1)
            header = json.loads(lines[0])
            self.assertEqual(header["schema_version"], "4.0")

    def test_skip_detectors(self):
        with tempfile.TemporaryDirectory() as d:
            input_path = os.path.join(d, "in.json")
            output_path = os.path.join(d, "out.jsonl")
            write_fake_session(input_path)

            bundle = pipeline_run(
                input_path, output_path, config_path=CONFIG_PATH,
                skip_detectors=True, quiet=True,
            )
            self.assertEqual(bundle.state_machine["phases"], [])
            self.assertEqual(bundle.constraint_events, [])
            self.assertIn("detectors skipped", bundle.detector_meta["warnings"])

    def test_review_contract_violation_with_spec(self):
        """spec 含 subagents.review-agent 时，缺 passed 字段应被检测。"""
        with tempfile.TemporaryDirectory() as d:
            input_path = os.path.join(d, "in.json")
            output_path = os.path.join(d, "out.jsonl")
            spec_dir = os.path.join(d, "specs")
            os.makedirs(spec_dir)
            with open(os.path.join(spec_dir, "subagents.yaml"), "w", encoding="utf-8") as f:
                f.write("review-agent:\n  required_fields: [passed, retryAdvice]\n")
            write_fake_session(input_path)

            bundle = pipeline_run(
                input_path, output_path, config_path=CONFIG_PATH,
                spec_dir=spec_dir, quiet=True,
            )
            issues = [e["issue"] for e in bundle.constraint_events if e["kind"] == "review_contract"]
            self.assertIn("missing_required_field", issues)

    def test_truncate_default_on(self):
        """默认 truncate_enabled = True，ai_text 大文本应被截断。"""
        with tempfile.TemporaryDirectory() as d:
            input_path = os.path.join(d, "in.json")
            output_path = os.path.join(d, "out.jsonl")
            write_fake_session(input_path)

            bundle = pipeline_run(
                input_path, output_path, config_path=CONFIG_PATH, quiet=True,
            )
            ai_text_entries = [e for e in bundle.trace if e.get("entry_class") == "ai_text"]
            long_ones = [e for e in ai_text_entries
                         if e.get("message", {}).get("content", [{}])[0].get("text", "").startswith("<think>")]
            self.assertGreater(len(long_ones), 0)
            truncated_text = long_ones[0]["message"]["content"][0]["text"]
            self.assertIn("truncated", truncated_text)


# ---------------------------------------------------------------------------
# 第二层：真实样本 e2e（需 RUN_REAL=1）
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    os.environ.get("RUN_REAL") == "1",
    "真实样本测试需 RUN_REAL=1 才运行",
)
@unittest.skipUnless(
    os.path.exists(REAL_SESSION),
    f"真实样本不存在：{REAL_SESSION}",
)
class TestE2ERealSession(unittest.TestCase):
    """真实样本端到端测试 — 1b4c0c37 上验证 detector 信号密度。"""

    def test_real_session_signals(self):
        with tempfile.TemporaryDirectory() as d:
            output_path = os.path.join(d, "out.jsonl")
            bundle = pipeline_run(
                input_path=REAL_SESSION,
                output_path=output_path,
                config_path=CONFIG_PATH,
                spec_dir=SPECS_DIR,
                quiet=True,
            )

            self.assertEqual(bundle.schema_version, "4.0")
            self.assertEqual(bundle.session["sessionId"],
                             "1b4c0c37-23cc-4e75-9eb9-125629d9d274")
            self.assertIn("phase0", bundle.state_machine["phases"])
            self.assertIn("phase4", bundle.state_machine["phases"])

            gate_events = [e for e in bundle.constraint_events
                           if e["kind"] == "gate_rejected"]
            self.assertGreaterEqual(len(gate_events), 1)
            self.assertEqual(gate_events[0]["phase"], "phase0")
            self.assertEqual(gate_events[0]["gate_script"], "phase0-pre-init-workdir")

            self.assertGreaterEqual(len(bundle.user_feedback), 4)
            self.assertIn("user_input", bundle.execution_pattern["step_counts"])
            self.assertTrue(bundle.detector_meta["spec_loaded"])

            with open(output_path, "r", encoding="utf-8") as f:
                header = json.loads(f.readline())
            self.assertEqual(header["schema_version"], "4.0")


# ---------------------------------------------------------------------------
# 第三层：v3 集成（默认跑）
# ---------------------------------------------------------------------------


class TestE2EIntegration(unittest.TestCase):
    """v3 集成测试 — 验证 classify + sort + save 的基础 pipeline 流程。"""

    def test_full_pipeline(self):
        """测试完整流程：加载 -> 分类 -> 排序 -> 保存（v3 子集）。"""
        test_data = [
            {"type": "queue-operation", "operation": "enqueue",
             "timestamp": "2026-05-09T03:07:09.950Z", "uuid": "1"},
            {"type": "user",
             "message": {"role": "user", "content": [{"type": "text", "text": "请跳过查询过程"}]},
             "timestamp": "2026-05-09T03:07:09.998Z", "uuid": "2"},
            {"type": "assistant",
             "message": {"role": "assistant",
                          "content": [{"type": "text", "text": "<think>思考过程\n\n明白，已跳过查询。"}],
                          "stop_reason": "end_turn"},
             "timestamp": "2026-05-09T03:07:15.310Z", "uuid": "3"},
            {"type": "last-prompt", "lastPrompt": "测试提示", "uuid": "4"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            for entry in test_data:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            input_file = f.name

        output_file = tempfile.mktemp(suffix=".jsonl")

        try:
            entries = load_session_entries(input_file)[0]
            self.assertEqual(len(entries), 4)

            for entry in entries:
                entry["entry_class"] = classify_entry(entry)

            self.assertEqual(entries[0]["entry_class"], "queue-operation")
            self.assertEqual(entries[1]["entry_class"], "user_input")
            self.assertEqual(entries[2]["entry_class"], "ai_text")
            self.assertEqual(entries[3]["entry_class"], "last-prompt")

            sorted_entries = sort_by_timestamp(entries)
            self.assertEqual(sorted_entries[0]["uuid"], "4")
            self.assertEqual(sorted_entries[1]["uuid"], "1")
            self.assertEqual(sorted_entries[2]["uuid"], "2")
            self.assertEqual(sorted_entries[3]["uuid"], "3")

            # 写回 NDJSON（内联避免抽 save_jsonl 单文件）
            with open(output_file, "w", encoding="utf-8") as f:
                for entry in sorted_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            with open(output_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 4)
                for line in lines:
                    entry = json.loads(line)
                    self.assertIn("entry_class", entry)
        finally:
            os.unlink(input_file)
            if os.path.exists(output_file):
                os.unlink(output_file)

    @unittest.skipUnless(
        os.path.exists(REAL_SESSION),
        f"真实样本不存在：{REAL_SESSION}",
    )
    def test_with_real_session(self):
        """使用真实 session 文件测试 v3 子流程（classify + sort + save_jsonl）。"""
        # 加载：load_session_entries 兼容 NDJSON / JSON 数组两种格式
        entries = load_session_entries(REAL_SESSION)[0]
        self.assertEqual(len(entries), 91)

        # 分类
        for entry in entries:
            entry["entry_class"] = classify_entry(entry)

        # 统计分类（classifier 已输出 attachment.{subtype}）
        from collections import Counter
        classes = Counter(entry["entry_class"] for entry in entries)
        # attachment.* 子类合计 21（v3 时代归类为 "attachment"）
        attachment_total = sum(v for k, v in classes.items() if k.startswith("attachment."))
        self.assertEqual(attachment_total, 21)
        self.assertEqual(classes["ai_tool_call"], 17)
        self.assertEqual(classes["tool_result"], 17)
        self.assertEqual(classes["ai_text"], 16)
        self.assertEqual(classes["user_input"], 4)
        self.assertEqual(classes["user_command"], 3)

        # 排序
        sorted_entries = sort_by_timestamp(entries)

        # 验证排序（检查时间戳是否递增）
        from src.util.timestamp import parse_timestamp
        for i in range(1, len(sorted_entries)):
            prev_time = parse_timestamp(sorted_entries[i - 1].get("timestamp", ""))
            curr_time = parse_timestamp(sorted_entries[i].get("timestamp", ""))
            self.assertLessEqual(prev_time, curr_time)

        # 保存 + 验证行数
        output_file = tempfile.mktemp(suffix=".jsonl")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                for entry in sorted_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            with open(output_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 91)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)


if __name__ == "__main__":
    unittest.main()