#!/usr/bin/env python3
"""
保存进化后的SKILL
"""

import sys
from pathlib import Path
from datetime import datetime


def save_evolved_skill(skills_dir: Path, skill_name: str, content: str) -> Path:
    """保存进化后的SKILL"""
    skill_dir = skills_dir / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = skill_dir / 'SKILL_v2.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return output_path


def main():
    if len(sys.argv) < 3:
        print("用法: python save_evolved_skill.py <skill_name> <content> [skills_dir]")
        print("  或: echo 'content' | python save_evolved_skill.py <skill_name> - [skills_dir]")
        sys.exit(1)
    
    skill_name = sys.argv[1]
    content_arg = sys.argv[2]
    skills_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('skills')
    
    # 从stdin读取内容
    if content_arg == '-':
        content = sys.stdin.read()
    else:
        content = content_arg
    
    if not skills_dir.exists():
        print(f"错误：skills目录不存在: {skills_dir}")
        sys.exit(1)
    
    try:
        output_path = save_evolved_skill(skills_dir, skill_name, content)
        print(f"进化后的SKILL已保存到: {output_path}")
    except Exception as e:
        print(f"错误：保存失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
