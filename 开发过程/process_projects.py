"""
process_projects.py — 遍历 projects/ 下所有 session，simplify 后写到 project_out/。

目录结构对应：
  projects/1dc55302-.../session.jsonl              →  project_out/1dc55302-.../session.jsonl
  projects/1dc55302-.../subagents/agent-xxx.jsonl  →  project_out/1dc55302-.../subagents/agent-xxx.jsonl

每个 session 用 v4 collector 的 pipeline.run 简化。
"""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

# 添加 session_extractor 路径
SESSION_EXTRACTOR_DIR = Path(__file__).parent / "session_extractor"
sys.path.insert(0, str(SESSION_EXTRACTOR_DIR))

from src.pipeline import run as pipeline_run  # noqa: E402


PROJECTS_DIR = Path(__file__).parent / "projects"
OUTPUT_DIR = Path(__file__).parent / "project_out"
CONFIG_PATH = SESSION_EXTRACTOR_DIR / "src" / "simplify" / "entry_fields_config.json"
SPEC_DIR = SESSION_EXTRACTOR_DIR / "specs"


def process_one_session(input_path: Path, output_path: Path) -> dict:
    """处理单个 session，写到 output_path。返回处理摘要。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bundle = pipeline_run(
        input_path=str(input_path),
        output_path=str(output_path),
        config_path=str(CONFIG_PATH),
        spec_dir=str(SPEC_DIR),
        quiet=True,
    )

    return {
        "input": str(input_path.relative_to(PROJECTS_DIR.parent)),
        "output": str(output_path.relative_to(OUTPUT_DIR.parent)),
        "size_in": input_path.stat().st_size,
        "size_out": output_path.stat().st_size if output_path.exists() else 0,
        "session_id": bundle.session.get("sessionId"),
        "trace_count": len(bundle.trace),
        "phases": bundle.state_machine.get("phases", []),
        "constraint_events": len(bundle.constraint_events),
        "user_feedback": len(bundle.user_feedback),
    }


def main():
    print("=" * 80)
    print(f"process_projects.py")
    print(f"输入目录: {PROJECTS_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 80)

    # 找所有 .jsonl
    jsonl_files = sorted(PROJECTS_DIR.rglob("*.jsonl"))
    if not jsonl_files:
        print(f"未找到任何 .jsonl 文件")
        return

    print(f"找到 {len(jsonl_files)} 个 session 文件\n")

    summaries = []
    for input_path in jsonl_files:
        # 计算输出路径：替换 projects/ 为 project_out/
        rel_path = input_path.relative_to(PROJECTS_DIR)
        output_path = OUTPUT_DIR / rel_path

        # 进度提示
        marker = "[MAIN]" if "subagents" not in str(input_path) else "  [SUB]"
        print(f"{marker} {rel_path}")
        print(f"   -> {output_path.relative_to(OUTPUT_DIR.parent)}")

        try:
            summary = process_one_session(input_path, output_path)
            summaries.append(summary)

            # 简明输出
            print(f"   size: {summary['size_in']} → {summary['size_out']} bytes")
            print(f"   session_id: {summary['session_id'][:36]}...")
            print(f"   trace: {summary['trace_count']} 条")
            print(f"   phases: {summary['phases']}")
            print(f"   constraint_events: {summary['constraint_events']} 条")
            print(f"   user_feedback: {summary['user_feedback']} 条")
            print()
        except Exception as e:
            print(f"   [ERROR] {e}\n")

    # 汇总
    print("=" * 80)
    print(f"完成: {len(summaries)}/{len(jsonl_files)} 成功")
    total_in = sum(s["size_in"] for s in summaries)
    total_out = sum(s["size_out"] for s in summaries)
    print(f"总体积: {total_in} → {total_out} bytes ({(total_in - total_out) / total_in * 100:.1f}% 节省)")
    print("=" * 80)


if __name__ == "__main__":
    main()
