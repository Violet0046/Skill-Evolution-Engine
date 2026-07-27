"""
infra/core/review_db/diffutil.py
后端预计算 line-level diff, 见 finalize 阶段用 difflib 算好, 存 see_evolution_change.linediff_json.

零外部依赖 (用 Python 标准库 difflib.SequenceMatcher).
"""
from __future__ import annotations

import difflib
from typing import Any

# 与前端 DiffViewer 期望的 kind 集合对齐
KIND_CONTEXT = "context"        # 双侧都有, 内容一样
KIND_REMOVED = "removed"        # 仅左栏, 红删
KIND_ADDED = "added"            # 仅右栏, 绿增
KIND_PLACEHOLDER = "placeholder"  # 对侧无对应行 (左栏 trailing 删除 / 右栏 trailing 新增)


def _split_lines(s: str) -> list[str]:
    """把 content 按行切. 空字符串 → [']. 末行不带 \\n."""
    if not s:
        return [""]
    return s.split("\n")


def compute_linediff(orig: str, new: str) -> dict[str, Any]:
    """
    计算行级 diff (前端可直接渲染):
      leftLines[i] = { lineNo, text, kind }
        - kind: 'removed'  → 删
              'context'   → 双侧一样, 左展示
              'placeholder' → 右栏对应行, 左留空
      rightLines[i] = { lineNo, text, kind }
        - kind: 'added'    → 增
              'context'   → 双侧一样, 右展示
              'placeholder' → 左栏对应行, 右留空
      added / removed   统计
    """
    left_raw = _split_lines(orig or "")
    right_raw = _split_lines(new or "")
    matcher = difflib.SequenceMatcher(a=left_raw, b=right_raw, autojunk=False)
    opcodes = matcher.get_opcodes()

    left_lines: list[dict[str, Any]] = []
    right_lines: list[dict[str, Any]] = []
    added = 0
    removed = 0

    o_line = 1
    n_line = 1

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for k in range(i2 - i1):
                txt = left_raw[i1 + k]
                left_lines.append({
                    "lineNo": o_line,
                    "text": txt,
                    "kind": KIND_CONTEXT,
                })
                right_lines.append({
                    "lineNo": n_line,
                    "text": txt,
                    "kind": KIND_CONTEXT,
                })
                o_line += 1
                n_line += 1
        elif tag == "delete":
            # i1..i2 是左栏独有 (删)
            for k in range(i1, i2):
                left_lines.append({
                    "lineNo": o_line,
                    "text": left_raw[k],
                    "kind": KIND_REMOVED,
                })
                # 右栏占位, 让左右对齐
                right_lines.append({
                    "lineNo": "",
                    "text": "",
                    "kind": KIND_PLACEHOLDER,
                })
                o_line += 1
                removed += 1
        elif tag == "insert":
            # j1..j2 是右栏独有 (增)
            for k in range(j1, j2):
                left_lines.append({
                    "lineNo": "",
                    "text": "",
                    "kind": KIND_PLACEHOLDER,
                })
                right_lines.append({
                    "lineNo": n_line,
                    "text": right_raw[k],
                    "kind": KIND_ADDED,
                })
                n_line += 1
                added += 1
        elif tag == "replace":
            # 左删 + 右增
            for k in range(i1, i2):
                left_lines.append({
                    "lineNo": o_line,
                    "text": left_raw[k],
                    "kind": KIND_REMOVED,
                })
                right_lines.append({
                    "lineNo": "",
                    "text": "",
                    "kind": KIND_PLACEHOLDER,
                })
                o_line += 1
                removed += 1
            for k in range(j1, j2):
                left_lines.append({
                    "lineNo": "",
                    "text": "",
                    "kind": KIND_PLACEHOLDER,
                })
                right_lines.append({
                    "lineNo": n_line,
                    "text": right_raw[k],
                    "kind": KIND_ADDED,
                })
                n_line += 1
                added += 1

    return {
        "leftLines": left_lines,
        "rightLines": right_lines,
        "added": added,
        "removed": removed,
    }
