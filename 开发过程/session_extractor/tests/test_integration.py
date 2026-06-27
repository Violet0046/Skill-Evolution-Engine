"""
集成测试
"""

import unittest
import sys
import os
import tempfile
import json

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.classifier import classify_entry
from src.timestamp import parse_timestamp, sort_by_timestamp
from src.utils import load_jsonl, save_jsonl


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_full_pipeline(self):
        """测试完整流程：加载 -> 分类 -> 排序 -> 保存"""
        # 创建测试数据
        test_data = [
            {
                "type": "queue-operation",
                "operation": "enqueue",
                "timestamp": "2026-05-09T03:07:09.950Z",
                "uuid": "1"
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请跳过查询过程"}
                    ]
                },
                "timestamp": "2026-05-09T03:07:09.998Z",
                "uuid": "2"
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "<think>思考过程</tool_call>\n\n明白，已跳过查询。"
                        }
                    ],
                    "stop_reason": "end_turn"
                },
                "timestamp": "2026-05-09T03:07:15.310Z",
                "uuid": "3"
            },
            {
                "type": "last-prompt",
                "lastPrompt": "测试提示",
                "uuid": "4"
            }
        ]
        
        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for entry in test_data:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            input_file = f.name
        
        output_file = tempfile.mktemp(suffix=".jsonl")
        
        try:
            # 加载
            entries = load_jsonl(input_file)
            self.assertEqual(len(entries), 4)
            
            # 分类
            for entry in entries:
                entry["entry_class"] = classify_entry(entry)
            
            # 验证分类
            self.assertEqual(entries[0]["entry_class"], "queue-operation")
            self.assertEqual(entries[1]["entry_class"], "user_input")
            self.assertEqual(entries[2]["entry_class"], "ai_text")
            self.assertEqual(entries[3]["entry_class"], "last-prompt")
            
            # 排序
            sorted_entries = sort_by_timestamp(entries)
            
            # 验证排序（last-prompt没有时间戳，排在最前面）
            self.assertEqual(sorted_entries[0]["uuid"], "4")
            self.assertEqual(sorted_entries[1]["uuid"], "1")
            self.assertEqual(sorted_entries[2]["uuid"], "2")
            self.assertEqual(sorted_entries[3]["uuid"], "3")
            
            # 保存
            save_jsonl(sorted_entries, output_file)
            
            # 验证保存的文件
            with open(output_file, "r") as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 4)
                
                # 验证每行都有entry_class字段
                for line in lines:
                    entry = json.loads(line)
                    self.assertIn("entry_class", entry)
        
        finally:
            os.unlink(input_file)
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_with_real_session(self):
        """使用真实的session文件测试"""
        input_file = "/home/10358563/Code/session_extractor/1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl"

        if not os.path.exists(input_file):
            self.skipTest("真实session文件不存在")

        output_file = tempfile.mktemp(suffix=".jsonl")

        try:
            # 加载：兼容 NDJSON 与 JSON 数组（v3 的 session_simplifier 行为）
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read()
            if text.lstrip().startswith("["):
                data = json.loads(text)
                entries = [e for e in data if isinstance(e, dict)]
            else:
                entries = load_jsonl(input_file)
            self.assertEqual(len(entries), 91)

            # 分类
            for entry in entries:
                entry["entry_class"] = classify_entry(entry)

            # 统计分类
            from collections import Counter
            classes = Counter(entry["entry_class"] for entry in entries)

            # 验证分类统计
            self.assertEqual(classes["attachment"], 21)
            self.assertEqual(classes["ai_tool_call"], 17)
            self.assertEqual(classes["tool_result"], 17)
            self.assertEqual(classes["ai_text"], 16)
            self.assertEqual(classes["user_input"], 4)
            self.assertEqual(classes["user_command"], 3)

            # 排序
            sorted_entries = sort_by_timestamp(entries)

            # 验证排序（检查时间戳是否递增）
            for i in range(1, len(sorted_entries)):
                prev_time = parse_timestamp(sorted_entries[i-1].get("timestamp", ""))
                curr_time = parse_timestamp(sorted_entries[i].get("timestamp", ""))
                self.assertLessEqual(prev_time, curr_time)

            # 保存
            save_jsonl(sorted_entries, output_file)

            # 验证保存的文件
            with open(output_file, "r") as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 91)

        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)


if __name__ == "__main__":
    unittest.main()
