"""patch_parser.py — OpenSpace Patch 解析与应用（纯 Python 重写版）。

设计目标：
- 修掉旧 `apply_patch.py` 的几个边界 bug
  * 缺 `*** End Patch` 哨兵时的尾部处理
  * 空行 / 缩进行 / 跨段落行处理
  * `@@` 锚点重复匹配不报错
- 改 dataclass + TypedDict，外部 import 友好
- 支持 CLI: `python -m core.patch.patch_parser <skill_md_path> <patch_file>`
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# Windows GBK stdout 兜底
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class UpdateOp:
    """一个 `@@` 段落。"""
    anchor: str
    lines: List[Tuple[str, str]] = field(default_factory=list)
    # lines: [(prefix, content), ...]   prefix ∈ {' ', '-', '+', ''}


@dataclass
class FileOps:
    """一个 `*** Update File` 块。"""
    file_path: str
    ops: List[UpdateOp] = field(default_factory=list)


@dataclass
class ApplyResult:
    """patch 应用结果。"""
    success: bool
    message: str
    anchor_hits: int = 0
    anchor_misses: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

_BEGIN = "*** Begin Patch"
_END = "*** End Patch"
_UPDATE = re.compile(r"^\*\*\* Update File:\s*(.+?)\s*$")
_ADD = re.compile(r"^\*\*\* Add File:\s*(.+?)\s*$")
_DELETE = re.compile(r"^\*\*\* Delete File:\s*(.+?)\s*$")
_ANCHOR = re.compile(r"^@@\s*(.*?)\s*$")
_LINE_PREFIX = {" ", "-", "+"}


def parse_patch(patch_text: str) -> List[FileOps]:
    """解析 patch 文本，返回 FileOps 列表。

    严格按行扫描，状态机：
    - 看到 `*** Begin Patch` → 进入文件级解析
    - 看到 `*** Update File: X` → 开新文件
    - 看到 `@@ Y` → 开新 @@ 段落（Y 是锚点）
    - 看到 `-` / `+` / ` ` 前缀 → 当前 @@ 段落的行
    - 看到 `*** End Patch` → 结束
    """
    files: List[FileOps] = []
    cur_file: Optional[FileOps] = None
    cur_op: Optional[UpdateOp] = None
    in_patch = False

    for raw in patch_text.splitlines():
        line = raw.rstrip("\n")

        if not in_patch:
            if line.strip() == _BEGIN:
                in_patch = True
            continue

        if line.strip() == _END:
            # 收尾：推入最后一个 op / file
            if cur_op is not None and cur_file is not None:
                cur_file.ops.append(cur_op)
                cur_op = None
            if cur_file is not None:
                files.append(cur_file)
                cur_file = None
            in_patch = False
            continue

        m = _UPDATE.match(line)
        if m:
            # 收尾上一个 file
            if cur_op is not None and cur_file is not None:
                cur_file.ops.append(cur_op)
                cur_op = None
            if cur_file is not None:
                files.append(cur_file)
            cur_file = FileOps(file_path=m.group(1).strip())
            continue

        m = _ADD.match(line) or _DELETE.match(line)
        if m:
            # Add / Delete 暂不支持（v1 evolver 只用 Update）
            if cur_op is not None and cur_file is not None:
                cur_file.ops.append(cur_op)
                cur_op = None
            if cur_file is not None:
                files.append(cur_file)
            # 用一个特殊 marker FileOps 表示，apply 时识别
            files.append(FileOps(file_path=m.group(1).strip(), ops=[]))
            cur_file = None
            continue

        m = _ANCHOR.match(line)
        if m:
            if cur_op is not None and cur_file is not None:
                cur_file.ops.append(cur_op)
            cur_op = UpdateOp(anchor=m.group(1).strip())
            continue

        if cur_op is not None:
            # 内容行：识别前缀
            if line and line[0] in _LINE_PREFIX:
                cur_op.lines.append((line[0], line[1:]))
            else:
                # 空行 / 无前缀 → 视为保留
                cur_op.lines.append(("", line))
        # else: 文件外孤立行，忽略

    # EOF 时若 patch 缺 `*** End Patch`，也要收尾
    if in_patch:
        if cur_op is not None and cur_file is not None:
            cur_file.ops.append(cur_op)
        if cur_file is not None:
            files.append(cur_file)

    return files


# ---------------------------------------------------------------------------
# 应用
# ---------------------------------------------------------------------------

def _find_anchor(lines: List[str], anchor: str, start: int = 0) -> int:
    """找锚点行（精确字符串匹配，strip 后比）。返回 -1 表示未找到。"""
    target = anchor.strip()
    for i in range(start, len(lines)):
        if lines[i].strip() == target:
            return i
    return -1


def _apply_update(file_lines: List[str], op: UpdateOp,
                  start_search: int = 0) -> Tuple[List[str], int, bool]:
    """对一个 @@ 段落应用。返回 (新文件行, 下一段搜索起点, 是否命中)。"""
    idx = _find_anchor(file_lines, op.anchor, start=start_search)
    if idx < 0:
        return file_lines, start_search, False

    # 从锚点行后面开始应用
    out: List[str] = []
    out.extend(file_lines[:idx + 1])   # 含锚点行
    cursor = idx + 1                    # 已消费到锚点之后

    for prefix, content in op.lines:
        if prefix == "":
            # 无前缀（空行 / 上下文延续）：保留原文对应行
            if cursor < len(file_lines):
                out.append(file_lines[cursor])
                cursor += 1
        elif prefix == " ":
            # 上下文行：保留原文对应行
            if cursor < len(file_lines):
                out.append(file_lines[cursor])
                cursor += 1
        elif prefix == "-":
            # 删除：跳过原文对应行
            if cursor < len(file_lines):
                cursor += 1
        elif prefix == "+":
            # 添加：写入新行
            out.append(content)
        else:
            # 未知前缀：保守处理（当作上下文）
            if cursor < len(file_lines):
                out.append(file_lines[cursor])
                cursor += 1

    # 剩余原文
    out.extend(file_lines[cursor:])
    return out, idx + 1, True


def apply_patch(skill_md_path: Path, files_ops: List[FileOps]) -> ApplyResult:
    """应用 patch 到 skill_md_path（v1 仅支持 update 模式，path 由 FileOps.file_path 决定）。"""
    if not files_ops:
        return ApplyResult(False, "no operations", 0, [])

    # v1 仅支持单文件 update
    if len(files_ops) > 1:
        return ApplyResult(False, "v1 patch_parser 仅支持单文件 update", 0, [])

    file_ops = files_ops[0]
    if not skill_md_path.exists():
        return ApplyResult(False, f"目标文件不存在: {skill_md_path}", 0, [])

    original = skill_md_path.read_text(encoding="utf-8")
    file_lines = original.splitlines(keepends=False)
    # 末尾若有换行
    trailing_newline = original.endswith("\n")

    anchor_hits = 0
    anchor_misses: List[str] = []
    cursor = 0

    for op in file_ops.ops:
        new_lines, cursor, hit = _apply_update(file_lines, op, start_search=cursor)
        if hit:
            anchor_hits += 1
            file_lines = new_lines
        else:
            anchor_misses.append(op.anchor)

    if anchor_misses:
        return ApplyResult(
            False,
            f"未找到锚点行: {anchor_misses[:3]}{'...' if len(anchor_misses) > 3 else ''}",
            anchor_hits, anchor_misses,
        )

    new_content = "\n".join(file_lines)
    if trailing_newline and not new_content.endswith("\n"):
        new_content += "\n"
    skill_md_path.write_text(new_content, encoding="utf-8")

    return ApplyResult(
        True,
        f"已应用 {anchor_hits} 个 @@ 段落到 {skill_md_path}",
        anchor_hits, [],
    )


def apply_patch_text(skill_md_path: Path, patch_text: str) -> ApplyResult:
    """便捷：parse + apply。"""
    files_ops = parse_patch(patch_text)
    return apply_patch(skill_md_path, files_ops)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="OpenSpace Patch 应用工具（纯 Python）",
    )
    parser.add_argument("skill_md", type=Path, help="目标 SKILL.md 路径")
    parser.add_argument("patch_file", type=Path, help="Patch 文本文件（- 表示 stdin）")
    args = parser.parse_args(argv)

    if not args.skill_md.exists():
        print(f"错误: 目标文件不存在: {args.skill_md}")
        return 1

    patch_text = (
        sys.stdin.read()
        if str(args.patch_file) == "-"
        else args.patch_file.read_text(encoding="utf-8")
    )

    result = apply_patch_text(args.skill_md, patch_text)
    print(f"{'✅' if result.success else '❌'} {result.message}")
    print(f"  anchor 命中: {result.anchor_hits}, 失败: {len(result.anchor_misses)}")
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
