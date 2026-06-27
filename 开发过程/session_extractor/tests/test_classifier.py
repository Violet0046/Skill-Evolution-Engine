"""
测试分类器
"""

import unittest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.util.classifier import classify_entry


class TestClassifier(unittest.TestCase):
    """测试分类器"""
    
    def test_system_event(self):
        """测试system类型分类"""
        # system类型
        entry = {"type": "system", "subtype": "stop_hook_summary"}
        self.assertEqual(classify_entry(entry), "system")
        
        # queue-operation类型
        entry = {"type": "queue-operation", "operation": "enqueue"}
        self.assertEqual(classify_entry(entry), "queue-operation")
        
        # last-prompt类型
        entry = {"type": "last-prompt", "lastPrompt": "test"}
        self.assertEqual(classify_entry(entry), "last-prompt")
        
        # attachment类型 — 应细化为 attachment.hook_success
        entry = {"type": "attachment", "attachment": {"type": "hook_success"}}
        self.assertEqual(classify_entry(entry), "attachment.hook_success")

    def test_attachment(self):
        """测试 attachment 细化为 attachment.{subtype}。"""
        # hook_success → attachment.hook_success
        entry = {"type": "attachment", "attachment": {"type": "hook_success"}}
        self.assertEqual(classify_entry(entry), "attachment.hook_success")

        # todo_reminder → attachment.todo_reminder
        entry = {"type": "attachment", "attachment": {"type": "todo_reminder"}}
        self.assertEqual(classify_entry(entry), "attachment.todo_reminder")

        # skill_listing → attachment.skill_listing
        entry = {"type": "attachment", "attachment": {"type": "skill_listing"}}
        self.assertEqual(classify_entry(entry), "attachment.skill_listing")

        # attachment 缺 type 字段 → 兜底返回 "attachment"（不细化）
        entry = {"type": "attachment"}
        self.assertEqual(classify_entry(entry), "attachment")
    
    def test_user_command(self):
        """测试user_command分类"""
        # 字符串形式
        entry = {
            "type": "user",
            "message": {
                "role": "user",
                "content": "<local-command-caveat>Caveat</local-command-caveat>"
            }
        }
        self.assertEqual(classify_entry(entry), "user_command")
        
        # 数组形式（content数组中的text应该返回user_input，而不是user_command）
        entry = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "<command-name>/model</command-name>"
                    }
                ]
            }
        }
        # 根据用户的要求，content数组中的text应该返回user_input
        self.assertEqual(classify_entry(entry), "user_input")
    
    def test_user_input(self):
        """测试user_input分类"""
        entry = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请跳过查询过程，已有相关需求信息"
                    }
                ]
            }
        }
        self.assertEqual(classify_entry(entry), "user_input")
    
    def test_user_input_should_not_be_user_command(self):
        """测试content数组中的text不应该被分类为user_command"""
        entry = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "<command-name>/model</command-name>"
                    }
                ]
            }
        }
        # content数组中的text应该返回user_input，而不是user_command
        self.assertEqual(classify_entry(entry), "user_input")
    
    def test_tool_result(self):
        """测试tool_result分类"""
        entry = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "content": "文件内容"
                    }
                ]
            }
        }
        self.assertEqual(classify_entry(entry), "tool_result")
    
    def test_ai_text(self):
        """测试ai_text分类"""
        entry = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "<think>思考过程</think>\n\n回复内容"
                    }
                ]
            }
        }
        self.assertEqual(classify_entry(entry), "ai_text")
    
    def test_ai_tool_call(self):
        """测试ai_tool_call分类"""
        entry = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_123",
                        "name": "Bash",
                        "input": {"command": "ls -la"}
                    }
                ]
            }
        }
        self.assertEqual(classify_entry(entry), "ai_tool_call")


if __name__ == "__main__":
    unittest.main()
