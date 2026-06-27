"""
user_confirmation detector 单测。
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.detectors.user_confirmation import UserConfirmationDetector
from src.models import ClassifiedEntry, DetectorContext
from tests._detector_helpers import user_input


class TestUserConfirmationDetector(unittest.TestCase):
    def setUp(self):
        self.det = UserConfirmationDetector()
        self.ctx = DetectorContext()

    def test_empty_input(self):
        self.assertEqual(self.det.run([], self.ctx), [])

    def test_interrupted_event(self):
        entries = [user_input("u1", text="[Request interrupted by user]")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["mode"], "interrupted")
        self.assertEqual(out[0]["trigger"], "[Request interrupted...]")

    def test_auto_confirm_marker(self):
        entries = [user_input("u1", text="[auto-confirm] proceed")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["mode"], "auto_confirm")
        self.assertEqual(out[0]["trigger"], "[auto-confirm]")

    def test_auto_confirm_marker_with_env(self):
        entries = [user_input("u1", text="[auto-confirm] proceed")]
        ctx = DetectorContext(env={"AUTO_CONFIRM": "1"})
        out = self.det.run(entries, ctx)
        self.assertEqual(out[0]["auto_confirm_env"], "1")

    def test_permission_mode_explicit(self):
        entries = [user_input("u1", text="hello", permission_mode="acceptEdits")]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["mode"], "explicit_acceptEdits")
        self.assertEqual(out[0]["trigger"], "permissionMode")

    def test_normal_user_input_no_event(self):
        entries = [user_input("u1", text="please analyze X")]
        self.assertEqual(self.det.run(entries, self.ctx), [])

    def test_spec_auto_confirm_keys(self):
        entries = [user_input("u1", text="[auto-confirm]")]
        ctx = DetectorContext(
            env={"MY_AUTO_FLAG": "yes"},
            spec={"environment": {"auto_confirm_keys": ["MY_AUTO_FLAG"]}},
        )
        out = self.det.run(entries, ctx)
        self.assertEqual(out[0]["auto_confirm_env"], "yes")

    def test_real_sample_interrupted_marker(self):
        """1b4c0c37 真实样本含 [Request interrupted by user] 类型。"""
        entries = [
            user_input("u1", text="[Request interrupted by user for tool use]"),
        ]
        out = self.det.run(entries, self.ctx)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["mode"], "interrupted")


if __name__ == "__main__":
    unittest.main()