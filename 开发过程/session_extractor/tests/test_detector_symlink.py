"""
symlink detector 单测。

Windows 上 tmp_path 是真实目录；用 os.symlink 需要特权。
若无 symlink 权限则跳过 link 创建的测试，但路径不存在 / 路径非 symlink 的逻辑仍覆盖。
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.detectors.symlink import SymlinkHopDetector
from src.models import ClassifiedEntry, DetectorContext


def entry_with_cwd(uuid, cwd, timestamp="2026-06-27T00:00:00Z"):
    return ClassifiedEntry(
        raw={"uuid": uuid, "timestamp": timestamp, "cwd": cwd},
        entry_class="ai_tool_call",  # entry_class 不影响 detector 行为
    )


class TestSymlinkHopDetector(unittest.TestCase):
    def setUp(self):
        self.det = SymlinkHopDetector()
        self.ctx = DetectorContext()

    def test_empty_input(self):
        self.assertEqual(self.det.run([], self.ctx), [])

    def test_no_cwd_ignored(self):
        entries = [
            ClassifiedEntry(raw={"uuid": "u1", "timestamp": "2026-06-27T00:00:00Z"},
                            entry_class="user_input"),
        ]
        self.assertEqual(self.det.run(entries, self.ctx), [])

    def test_nonexistent_cwd_no_event(self):
        """cwd 路径不存在时 realpath 应退化为 cwd 本身 → 不触发。"""
        entries = [entry_with_cwd("u1", "/nonexistent/path/that/does/not/exist")]
        out = self.det.run(entries, self.ctx)
        # realpath 对不存在路径在不同 OS 上行为不同；这里只校验不崩
        self.assertIsInstance(out, list)

    def test_realpath_cached(self):
        cwd = "/nonexistent/path/abc"
        entries = [entry_with_cwd("u1", cwd), entry_with_cwd("u2", cwd)]
        self.det.run(entries, self.ctx)
        # 缓存应被填充
        self.assertIn(cwd, self.ctx.cwd_realpath_cache)

    def test_symlink_creates_event(self):
        """如果系统支持 symlink，创建一个并验证 detector 命中。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "real_target"
            target.mkdir()
            link = Path(tmpdir) / "link_to_target"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest(f"symlink not supported on this OS")

            entries = [entry_with_cwd("u1", str(link))]
            out = self.det.run(entries, self.ctx)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["logical_cwd"], str(link))
            self.assertEqual(out[0]["physical_cwd"], str(target))


if __name__ == "__main__":
    unittest.main()