#!/usr/bin/env python3
"""
分析具体证据，获取完整的工具调用信息
"""

import json
import sys
from pathlib import Path


def find_tool_call(output_dir: Path, session_id: str, uuid: str) -> dict:
    """在output目录中查找指定的工具调用"""
    session_dir = output_dir / session_id
    if not session_dir.exists():
        return None
    
    skills_dir = session_dir / 'skills'
    if not skills_dir.exists():
        return None
    
    for skill_file in skills_dir.glob('*.json'):
        with open(skill_file, 'r', encoding='utf-8') as f:
            skill = json.load(f)
        
        for tc in skill.get('tool_calls', []):
            if tc.get('uuid') == uuid:
                return {
                    'skill_name': skill.get('skill_name'),
                    'tool_call': tc,
                }
    
    return None


def format_tool_call(result: dict) -> str:
    """格式化工具调用信息"""
    lines = []
    lines.append(f"# 工具调用详情")
    lines.append("")
    
    skill_name = result.get('skill_name', 'N/A')
    tc = result.get('tool_call', {})
    
    lines.append(f"## 基本信息")
    lines.append(f"- Skill名称：{skill_name}")
    lines.append(f"- 工具名称：{tc.get('tool_name', 'N/A')}")
    lines.append(f"- UUID：{tc.get('uuid', 'N/A')}")
    lines.append(f"- 时间戳：{tc.get('timestamp', 'N/A')}")
    lines.append(f"- 成功：{tc.get('success', False)}")
    lines.append(f"- 耗时：{tc.get('duration_ms', 'N/A')} ms")
    lines.append("")
    
    lines.append(f"## 输入信息")
    lines.append(f"- 输入摘要：{tc.get('input_summary', 'N/A')}")
    lines.append("")
    
    lines.append(f"## 输出信息")
    lines.append(f"- 输出摘要：{tc.get('output_summary', 'N/A')}")
    lines.append("")
    
    lines.append(f"## 错误信息")
    lines.append(f"- 错误消息：{tc.get('error_message', 'N/A')}")
    lines.append(f"- 错误输出：{tc.get('error_output', 'N/A')}")
    lines.append("")
    
    lines.append(f"## 推理过程")
    reasoning = tc.get('reasoning', 'N/A')
    if reasoning and reasoning != 'N/A':
        # 截取前500字符
        if len(reasoning) > 500:
            reasoning = reasoning[:500] + '...'
    lines.append(f"- 推理：{reasoning}")
    lines.append("")
    
    # Agent信息
    if tc.get('agent_id'):
        lines.append(f"## Agent信息")
        lines.append(f"- Agent ID：{tc.get('agent_id', 'N/A')}")
        lines.append(f"- Agent类型：{tc.get('agent_type', 'N/A')}")
        lines.append("")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("用法: python analyze_evidence.py <session_id> <uuid> [output_dir]")
        sys.exit(1)
    
    session_id = sys.argv[1]
    uuid = sys.argv[2]
    output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('output')
    
    if not output_dir.exists():
        print(f"错误：输出目录不存在: {output_dir}")
        sys.exit(1)
    
    result = find_tool_call(output_dir, session_id, uuid)
    
    if result:
        print(format_tool_call(result))
    else:
        print(f"错误：未找到工具调用 (session_id={session_id}, uuid={uuid})")
        sys.exit(1)


if __name__ == '__main__':
    main()
