#!/usr/bin/env python3
"""
读取原始SKILL定义
"""

import sys
from pathlib import Path


def read_skill(skill_file: Path) -> str:
    """读取SKILL定义"""
    with open(skill_file, 'r', encoding='utf-8') as f:
        return f.read()


def main():
    if len(sys.argv) < 2:
        print("用法: python read_skill.py <skill_file>")
        sys.exit(1)
    
    skill_file = Path(sys.argv[1])
    
    if not skill_file.exists():
        print(f"错误：SKILL文件不存在: {skill_file}")
        sys.exit(1)
    
    try:
        content = read_skill(skill_file)
        print(content)
    except Exception as e:
        print(f"错误：读取SKILL文件失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
