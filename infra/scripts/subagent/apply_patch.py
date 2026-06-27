#!/usr/bin/env python3
"""
Patch 应用脚本
解析并应用 OpenSpace 格式的 Patch 到 SKILL.md 文件
"""

import re
import sys
from pathlib import Path


def parse_patch(patch_content: str) -> list:
    """解析 Patch 内容
    
    返回: [(file_path, operations), ...]
    operations: [(type, anchor, lines), ...]
    type: 'update' | 'add' | 'delete'
    """
    files = []
    current_file = None
    current_ops = []
    current_anchor = None
    current_lines = []
    
    for line in patch_content.split('\n'):
        line = line.rstrip()
        
        # 开始 Patch
        if line == '*** Begin Patch':
            continue
        
        # 结束 Patch
        if line == '*** End Patch':
            # 处理最后一个操作
            if current_anchor and current_lines:
                current_ops.append(('update', current_anchor, current_lines))
                current_anchor = None
                current_lines = []
            # 处理最后一个文件
            if current_file and current_ops:
                files.append((current_file, current_ops))
                current_file = None
                current_ops = []
            break
        
        # 文件操作
        if line.startswith('*** Update File:'):
            if current_file and current_ops:
                files.append((current_file, current_ops))
            current_file = line.split(':', 1)[1].strip()
            current_ops = []
            current_anchor = None
            current_lines = []
            continue
        
        if line.startswith('*** Add File:'):
            if current_file and current_ops:
                files.append((current_file, current_ops))
            current_file = line.split(':', 1)[1].strip()
            current_ops = [('add', None, [])]
            current_lines = current_ops[0][2]
            continue
        
        if line.startswith('*** Delete File:'):
            if current_file and current_ops:
                files.append((current_file, current_ops))
            current_file = line.split(':', 1)[1].strip()
            current_ops = [('delete', None, [])]
            continue
        
        # 锚点行
        if line.startswith('@@'):
            if current_anchor is not None and current_lines:
                current_ops.append(('update', current_anchor, current_lines))
            current_anchor = line[2:].strip()
            current_lines = []
            continue
        
        # 内容行
        if line and line[0] in ['-', '+', ' ']:
            current_lines.append(line)
            continue
        
        # 空行或其他
        if current_lines:
            current_lines.append(line)
    
    # 处理最后一个文件的最后一个操作
    if current_anchor and current_lines:
        current_ops.append(('update', current_anchor, current_lines))
        current_anchor = None
        current_lines = []
    
    # 处理最后一个文件
    if current_file and current_ops:
        files.append((current_file, current_ops))
    
    return files


def apply_update(original: str, operations: list) -> str:
    """应用 update 操作到原始内容"""
    lines = original.split('\n')
    result = []
    i = 0
    
    for op_type, anchor, op_lines in operations:
        if op_type != 'update':
            continue
        
        # 复制当前位置之前的行
        while i < len(lines):
            if lines[i].strip() == anchor.strip():
                break
            result.append(lines[i])
            i += 1
        
        if i >= len(lines):
            print(f"警告: 锚点行未找到: {anchor}")
            continue
        
        # 添加锚点行
        result.append(lines[i])
        i += 1
        
        # 应用操作
        for op_line in op_lines:
            if op_line.startswith('-'):
                # 删除行 - 跳过原始内容中的对应行
                if i < len(lines):
                    i += 1
            elif op_line.startswith('+'):
                # 添加行
                result.append(op_line[1:])
            elif op_line.startswith(' '):
                # 保持行 - 从原始内容中读取
                if i < len(lines):
                    result.append(lines[i])
                    i += 1
    
    # 添加剩余的行
    while i < len(lines):
        result.append(lines[i])
        i += 1
    
    return '\n'.join(result)


def apply_add(original: str, operations: list) -> str:
    """应用 add 操作（添加新文件）"""
    for op_type, anchor, op_lines in operations:
        if op_type == 'add':
            return '\n'.join(line[1:] if line.startswith('+') else line for line in op_lines)
    return original


def apply_patch_to_file(file_path: Path, operations: list) -> bool:
    """应用 Patch 到指定文件"""
    try:
        if file_path.exists():
            original = file_path.read_text(encoding='utf-8')
        else:
            original = ''
        
        # 检查操作类型
        op_types = set(op_type for op_type, _, _ in operations)
        
        if 'delete' in op_types:
            # 删除文件
            if file_path.exists():
                file_path.unlink()
                print(f"已删除: {file_path}")
            return True
        
        if 'add' in op_types:
            # 添加新文件
            content = apply_add(original, operations)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            print(f"已创建: {file_path}")
            return True
        
        if 'update' in op_types:
            # 更新文件
            content = apply_update(original, operations)
            file_path.write_text(content, encoding='utf-8')
            print(f"已更新: {file_path}")
            return True
        
        return False
    
    except Exception as e:
        print(f"错误: 应用 Patch 失败 {file_path}: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("用法: python apply_patch.py <patch_file> <skill_dir>")
        print("示例: python apply_patch.py patch.txt /path/to/skills/初始化")
        sys.exit(1)
    
    patch_file = Path(sys.argv[1])
    skill_dir = Path(sys.argv[2])
    
    if not patch_file.exists():
        print(f"错误: Patch 文件不存在: {patch_file}")
        sys.exit(1)
    
    if not skill_dir.exists():
        print(f"错误: Skill 目录不存在: {skill_dir}")
        sys.exit(1)
    
    # 读取 Patch 内容
    patch_content = patch_file.read_text(encoding='utf-8')
    
    # 解析 Patch
    files = parse_patch(patch_content)
    
    if not files:
        print("错误: 未找到有效的 Patch 操作")
        sys.exit(1)
    
    # 应用 Patch
    success_count = 0
    for file_path, operations in files:
        full_path = skill_dir / file_path
        if apply_patch_to_file(full_path, operations):
            success_count += 1
    
    print(f"\nPatch 应用完成: {success_count}/{len(files)} 个文件成功")
    
    if success_count < len(files):
        sys.exit(1)


if __name__ == '__main__':
    main()
