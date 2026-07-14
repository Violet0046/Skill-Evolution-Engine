"""
see-evolve.py — 阶段 3 单文件入口（per-target_file → 4 字段 JSON）

**职责单一**：输入 1 个 target_file → 输出 1 个 4 字段 JSON。

双键消费：
- target_file → 路径键（sub-agent 用此 Read 原文件）
- suggestions → ID 键（从 reports_dir 读）

**`.change` 文件**：sub-agent 用 `Write` 工具写到
`evidence/evolution_changes/<flatten_target_file>.change`
（路径由本脚本算好，通过 `{{CHANGE_OUTPUT_DIR}}/{{CHANGE_FILENAME}}` 占位符传过去）。

主 agent 工作流：
    1. evolve-discovery.py → 拿 target_files（一次性）
    2. for tf in target_files: see-evolve.py <tf>（循环）
    3. for call: Agent(**call)（循环）

调试模式（--output-prompt）：把组装好的 prompt 单独写到 .md 文件，方便人类查看。

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <target_file>
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <tf> --output-prompt /tmp/evolve_prompt.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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


_ROOT = Path(__file__).resolve().parents[2]
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))


DEFAULT_SKILLS_DIR = _ROOT / "skills"
DEFAULT_CHANGE_OUTPUT_DIR = _ROOT / "evidence" / "evolution_changes"
DEFAULT_REPORTS_DIR = _ROOT / "evidence" / "analysis_reports"


def _get_suggestions(target_file: str, reports_dir: Path) -> tuple[list[dict], str]:
    """拿 suggestions + target_skill（首条 suggestion 的）。"""
    from core.evolver.aggregate import get_suggestions_for_target
    raw = get_suggestions_for_target(reports_dir, target_file)
    clean = [{k: v for k, v in sg.items() if k not in ("target_skill", "target_file")}
             for sg in raw]
    target_skill = raw[0].get("target_skill", "") if raw else ""
    return clean, target_skill


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阶段 3 单文件入口：per-target_file → 4 字段 JSON",
    )
    parser.add_argument("target_file",
                        help="target_file 相对路径（如 skills/查询需求信息/SKILL.md）")
    parser.add_argument("--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR,
                        help=f"skills 根目录（默认 {DEFAULT_SKILLS_DIR}）")
    parser.add_argument("--change-output-dir", type=Path, default=DEFAULT_CHANGE_OUTPUT_DIR,
                        help=f".change 文件输出目录（默认 {DEFAULT_CHANGE_OUTPUT_DIR}）")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR,
                        help=f"analysis_reports 目录（默认 {DEFAULT_REPORTS_DIR}）")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="JSON 输出文件（默认 stdout）")
    parser.add_argument("--output-prompt", type=Path, default=None,
                        help="调试用：把 prompt 文本写到 .md 文件（不影响 stdout 输出）")
    args = parser.parse_args()

    from core.evolver.prompt_builder import build_agent_call

    suggestions, target_skill = _get_suggestions(args.target_file, args.reports_dir)

    agent_call = build_agent_call(
        target_file=args.target_file,
        suggestions=suggestions,
        skills_dir=args.skills_dir.resolve(),
        change_output_dir=args.change_output_dir.resolve(),
        target_skill=target_skill,
    )

    # 调试模式：写 prompt 文本
    if args.output_prompt:
        args.output_prompt.parent.mkdir(parents=True, exist_ok=True)
        args.output_prompt.write_text(agent_call["prompt"], encoding="utf-8")
        print(f"已写入 prompt: {args.output_prompt}", file=sys.stderr)

    # 主输出：4 字段 JSON（stdout 或 --output）
    payload = json.dumps(agent_call, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"已写入 JSON: {args.output}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())