"""
see-evolve.py — 阶段 3 单文件入口（per (subject_name, target_file) → 4 字段 JSON）

**职责单一**：输入 1 组 (subject_name, target_file) → 输出 1 个 4 字段 JSON。

路径解析：
- project_root = <SEE_PROJECTS_HOME>/<subject_name>
- 源文件绝对路径 = project_root / target_file → 填 {{TARGET_FILE}}（sub-agent 直接 Read）
- suggestions 从 reports_dir 按 (subject_name, target_file) 过滤

**`.change` 文件**：sub-agent 用 `Write` 工具写到
`evidence/evolution_changes/<subject_name>__<flatten_target_file>.change`
（路径由本脚本算好，通过 `{{CHANGE_OUTPUT_DIR}}/{{CHANGE_FILENAME}}` 占位符传过去）。

主 agent 工作流：
    1. evolve-discovery.py → 拿 targets（[{subject_name, target_file}]，一次性）
    2. for t in targets: see-evolve.py <subject_name> <target_file>（循环）
    3. for call: Agent(**call)（循环）

调试模式（--output-prompt）：把组装好的 prompt 单独写到 .md 文件，方便人类查看。

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <subject_name> <target_file>
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <subject_name> <tf> --output-prompt /tmp/evolve_prompt.md
"""

from __future__ import annotations

import argparse
import json
import os
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


DEFAULT_PROJECTS_HOME = Path(os.environ.get("SEE_PROJECTS_HOME", str(_ROOT / "subjects")))
DEFAULT_CHANGE_OUTPUT_DIR = _ROOT / "evidence" / "evolution_changes"
DEFAULT_REPORTS_DIR = _ROOT / "evidence" / "analysis_reports"


def _get_suggestions(subject_name: str, target_file: str, reports_dir: Path) -> list[dict]:
    """拿指定 (subject_name, target_file) 的 suggestions（已去冗余字段）。"""
    from core.evolver.aggregate import get_clean_suggestions_for_target
    return get_clean_suggestions_for_target(reports_dir, target_file, subject_name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阶段 3 单文件入口：per-target_file → 4 字段 JSON",
    )
    parser.add_argument("subject_name",
                        help="subject 名（= arch 文件名 stem，evolve-discovery 输出的 targets[].subject_name）")
    parser.add_argument("target_file",
                        help="相对项目根的路径（如 skills/查询需求信息/SKILL.md）")
    parser.add_argument("--projects-home", type=Path, default=DEFAULT_PROJECTS_HOME,
                        help=f"subjects 根目录（默认 SEE_PROJECTS_HOME 或 {DEFAULT_PROJECTS_HOME}）")
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

    suggestions = _get_suggestions(args.subject_name, args.target_file, args.reports_dir)
    project_root = (args.projects_home / args.subject_name).resolve()

    agent_call = build_agent_call(
        target_file=args.target_file,
        suggestions=suggestions,
        project_root=project_root,
        change_output_dir=args.change_output_dir.resolve(),
        subject_name=args.subject_name,
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