"""
测试工具函数
"""

import unittest
import sys
import os
import tempfile
import json

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils import load_jsonl, save_jsonl


class TestUtils(unittest.TestCase):
    """测试工具函数"""
    
    def test_load_jsonl(self):
        """测试加载JSONL文件"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type": "user", "uuid": "1"}\n')
            f.write('{"type": "assistant", "uuid": "2"}\n')
            f.write('\n')  # 空行
            f.write('{"type": "system", "uuid": "3"}\n')
            temp_file = f.name
        
        try:
            entries = load_jsonl(temp_file)
            self.assertEqual(len(entries), 3)
            self.assertEqual(entries[0]["uuid"], "1")
            self.assertEqual(entries[1]["uuid"], "2")
            self.assertEqual(entries[2]["uuid"], "3")
        finally:
            os.unlink(temp_file)
    
    def test_save_jsonl(self):
        """测试保存JSONL文件"""
        entries = [
            {"type": "user", "uuid": "1"},
            {"type": "assistant", "uuid": "2"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_file = f.name
        
        try:
            save_jsonl(entries, temp_file)
            
            # 读取并验证
            with open(temp_file, "r") as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 2)
                self.assertEqual(json.loads(lines[0])["uuid"], "1")
                self.assertEqual(json.loads(lines[1])["uuid"], "2")
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    unittest.main()
