#!/usr/bin/env python3
"""
获取所有skill名称
遍历output目录下的summary.json，提取所有涉及的skill名称
"""

import json
import sys
from pathlib import Path


def get_all_skills(output_dir: Path) -> list:
    """获取所有skill名称"""
    skills = set()
    
    for session_dir in output_dir.iterdir():
        if not session_dir.is_dir():
            continue
        
        skills_dir = session_dir / 'skills'
        if not skills_dir.exists():
            continue
        
        for skill_file in skills_dir.glob('*.json'):
            skills.add(skill_file.stem)
    
    return sorted(list(skills))


def main():
    if len(sys.argv) < 2:
        print("用法: python get_skills.py <output_dir>")
        sys.exit(1)
    
    output_dir = Path(sys.argv[1])
    
    if not output_dir.exists():
        print(f"错误：目录不存在: {output_dir}")
        sys.exit(1)
    
    skills = get_all_skills(output_dir)
    
    print(f"共找到 {len(skills)} 个skill:")
    for skill in skills:
        print(f"  - {skill}")


if __name__ == '__main__':
    main()
