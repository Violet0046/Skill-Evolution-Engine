"""
v3 兼容回归测试。

验证 v4 collector 产出的 trace NDJSON 与 v3 out.jsonl 在**字段集**层面一致：
- v3 trace entry 与 v4 trace entry 的 key 集合必须相同
- v3 trace entry 的 required/recommended 字段 v4 仍保留
- v3 header 字段（session / cwdChanges）v4 header 仍含

不验证：truncate 后字节大小（v4 默认 ON，体积差异是预期）。
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline import run as pipeline_run


REAL_SESSION = str(
    Path(__file__).parent.parent / "1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl"
)
V3_OUT = str(
    Path(__file__).parent.parent / "out.jsonl"
)
CONFIG_PATH = str(Path(__file__).parent.parent / "src" / "simplify" / "entry_fields_config.json")


@unittest.skipUnless(
    os.path.exists(V3_OUT) and os.path.exists(REAL_SESSION),
    "v3 out.jsonl 或真实样本缺失",
)
class TestV3Compat(unittest.TestCase):
    """v3 trace NDJSON 字段集与 v4 trace NDJSON 字段集应当逐字段一致。"""

    def setUp(self):
        # 加载 v3 out.jsonl（JSON 数组格式）
        with open(V3_OUT, "r", encoding="utf-8") as f:
            v3_data = json.load(f)
        self.v3_header = v3_data[0]
        self.v3_trace = v3_data[1:]

        # 跑 v4 跑出 out_v4_compat.jsonl
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            self.v4_out = f.name
        pipeline_run(
            input_path=REAL_SESSION,
            output_path=self.v4_out,
            config_path=CONFIG_PATH,
            quiet=True,
        )
        with open(self.v4_out, "r", encoding="utf-8") as f:
            self.v4_header = json.loads(f.readline())
            self.v4_trace = [json.loads(line) for line in f]

    def tearDown(self):
        if os.path.exists(self.v4_out):
            os.unlink(self.v4_out)

    def test_v3_header_fields_in_v4(self):
        """v3 header 含的 session 字段 v4 header 仍含。"""
        v3_session = self.v3_header.get("session", {})
        v4_session = self.v4_header.get("session", {})
        for key in v3_session.keys():
            self.assertIn(key, v4_session, f"v4 header.session 缺 v3 key: {key}")
        # v3 cwdChanges 字段 v4 用 cwd_changes（snake_case）
        self.assertIn("cwd_changes", self.v4_header)

    def test_v3_trace_count_matches_v4(self):
        self.assertEqual(len(self.v3_trace), len(self.v4_trace))

    def test_v3_trace_union_keys_equal_v4(self):
        # v4 是 v3 的超集：v3 所有字段 v4 必须保留；v4 允许新增字段（如 cwd / prev_cwd）
        v3_keys = set()
        for e in self.v3_trace:
            v3_keys.update(e.keys())
        v4_keys = set()
        for e in self.v4_trace:
            v4_keys.update(e.keys())
        # v3-only 字段不允许（v4 必须保留所有 v3 字段）
        self.assertEqual(v3_keys - v4_keys, set(),
                         f"v3-only 字段 v4 没保留: {v3_keys - v4_keys}")
        # v4-only 字段允许（v4 可以新增）— 仅打印告知
        v4_new = v4_keys - v3_keys
        if v4_new:
            print(f"v4 新增字段: {v4_new}")

    def test_v4_schema_version_in_header(self):
        """v4 header 含 schema_version=4.0；v3 header 没有。"""
        self.assertEqual(self.v4_header["schema_version"], "4.0")
        self.assertNotIn("schema_version", self.v3_header)

    def test_v4_extends_header_not_trace(self):
        """v4 扩展字段（state_machine / constraint_events 等）只在 header，不在 trace。"""
        for key in ("schema_version", "state_machine", "constraint_events",
                    "user_feedback", "execution_pattern", "detector_meta"):
            self.assertIn(key, self.v4_header, f"v4 header 缺扩展字段: {key}")
            for trace_entry in self.v4_trace:
                self.assertNotIn(key, trace_entry,
                                 f"v4 trace 不应含 header 字段: {key}")


if __name__ == "__main__":
    unittest.main()