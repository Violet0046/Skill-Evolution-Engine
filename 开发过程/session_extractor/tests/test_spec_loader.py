"""
src/spec_loader.py 单测。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.spec_loader import load_spec


class TestSpecLoader(unittest.TestCase):
    def test_none_dir_returns_empty(self):
        self.assertEqual(load_spec(None), {})

    def test_nonexistent_dir_returns_empty(self):
        self.assertEqual(load_spec("/nonexistent/path"), {})

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_spec(d), {})

    def test_full_load(self):
        """使用真实的 specs/ 目录测试。"""
        real_specs = Path(__file__).parent.parent / "specs"
        if not real_specs.exists():
            self.skipTest("specs/ 目录不存在")
        out = load_spec(str(real_specs))
        self.assertIn("spec", out)
        self.assertIn("hooks", out)
        self.assertIn("subagents", out)
        self.assertIn("constraints", out)
        self.assertEqual(out["spec"]["name"], "requirement_analysis")
        self.assertEqual(len(out["spec"]["phases"]), 5)
        # review-agent 配置正确加载
        self.assertIn("review-agent", out["subagents"])
        self.assertEqual(out["subagents"]["review-agent"]["retry_count"], 2)

    def test_partial_load_missing_files(self):
        """目录中只有 spec.yaml，没有其他文件。"""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "spec.yaml"), "w", encoding="utf-8") as f:
                f.write("name: test\nphases:\n  - name: phase1\n")
            out = load_spec(d)
            self.assertIn("spec", out)
            self.assertNotIn("hooks", out)
            self.assertNotIn("subagents", out)
            self.assertNotIn("constraints", out)


if __name__ == "__main__":
    unittest.main()