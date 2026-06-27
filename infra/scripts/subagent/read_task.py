#!/usr/bin/env python3
"""
读取任务文件并格式化输出
"""

import json
import sys
from pathlib import Path


def read_task(task_file: Path) -> dict:
    """读取任务文件"""
    with open(task_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_task(task: dict) -> str:
    """格式化任务信息"""
    lines = []
    lines.append(f"# 任务信息")
    lines.append("")
    lines.append(f"## 基本信息")
    lines.append(f"- Skill名称：{task.get('skill_name', 'N/A')}")
    lines.append(f"- 总session数：{task.get('total_sessions', 0)}")
    lines.append(f"- 总调用次数：{task.get('total_calls', 0)}")
    lines.append(f"- 失败调用次数：{task.get('failed_calls', 0)}")
    lines.append(f"- 失败率：{task.get('failure_rate', 0):.2%}")
    lines.append("")
    
    lines.append(f"## 失败模式")
    for i, pattern in enumerate(task.get('failure_patterns', []), 1):
        lines.append(f"### {i}. {pattern.get('pattern', 'N/A')}")
        lines.append(f"- 出现次数：{pattern.get('count', 0)}")
        lines.append(f"- 证据数量：{len(pattern.get('evidence', []))}")
        lines.append("")
        
        lines.append("**证据示例**：")
        for j, evidence in enumerate(pattern.get('evidence', [])[:3], 1):
            lines.append(f"{j}. Session: {evidence.get('session_id', 'N/A')}")
            lines.append(f"   UUID: {evidence.get('uuid', 'N/A')}")
            lines.append(f"   Tool: {evidence.get('tool_name', 'N/A')}")
            lines.append(f"   Input: {evidence.get('input_summary', 'N/A')[:60]}")
            lines.append(f"   Error: {evidence.get('error_output', 'N/A')[:60]}")
            lines.append("")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: python read_task.py <task_file>")
        sys.exit(1)
    
    task_file = Path(sys.argv[1])
    
    if not task_file.exists():
        print(f"错误：任务文件不存在: {task_file}")
        sys.exit(1)
    
    try:
        task = read_task(task_file)
        print(format_task(task))
    except Exception as e:
        print(f"错误：读取任务文件失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
