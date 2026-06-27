"""
测试时间戳解析与排序工具
"""

import unittest
import sys
import os
from datetime import datetime

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.util.timestamp import parse_timestamp, sort_by_timestamp


class TestTimestamp(unittest.TestCase):
    """测试时间戳解析与排序工具"""
    
    def test_parse_timestamp_with_z(self):
        """测试带Z的时间戳解析"""
        timestamp = "2026-05-09T03:07:09.950Z"
        result = parse_timestamp(timestamp)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 5)
        self.assertEqual(result.day, 9)
        self.assertEqual(result.hour, 3)
        self.assertEqual(result.minute, 7)
        self.assertEqual(result.second, 9)
        self.assertEqual(result.microsecond, 950000)
    
    def test_parse_timestamp_without_z(self):
        """测试不带Z的时间戳解析"""
        timestamp = "2026-05-09T03:07:09.950"
        result = parse_timestamp(timestamp)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.microsecond, 950000)
    
    def test_parse_timestamp_without_microseconds(self):
        """测试不带毫秒的时间戳解析"""
        timestamp = "2026-05-09T03:07:09"
        result = parse_timestamp(timestamp)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.microsecond, 0)
    
    def test_parse_timestamp_empty(self):
        """测试空时间戳解析"""
        result = parse_timestamp("")
        self.assertEqual(result, datetime.min)
    
    def test_parse_timestamp_invalid(self):
        """测试无效时间戳解析"""
        result = parse_timestamp("invalid")
        self.assertEqual(result, datetime.min)
    
    def test_sort_by_timestamp(self):
        """测试按时间戳排序"""
        entries = [
            {"type": "user", "timestamp": "2026-05-09T03:09:40.160Z", "uuid": "3"},
            {"type": "user", "timestamp": "2026-05-09T03:07:09.817Z", "uuid": "1"},
            {"type": "assistant", "timestamp": "2026-05-09T03:09:46.268Z", "uuid": "4"},
            {"type": "user", "timestamp": "2026-05-09T03:07:09.998Z", "uuid": "2"},
            {"type": "last-prompt", "uuid": "5"},  # 没有时间戳
        ]
        
        sorted_entries = sort_by_timestamp(entries)
        
        # 验证排序
        self.assertEqual(sorted_entries[0]["uuid"], "5")  # 没有时间戳的排在最前面
        self.assertEqual(sorted_entries[1]["uuid"], "1")
        self.assertEqual(sorted_entries[2]["uuid"], "2")
        self.assertEqual(sorted_entries[3]["uuid"], "3")
        self.assertEqual(sorted_entries[4]["uuid"], "4")


if __name__ == "__main__":
    unittest.main()
