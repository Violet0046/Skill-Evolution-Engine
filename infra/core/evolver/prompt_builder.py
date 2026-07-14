"""
prompt_builder.py — 组装 evolver sub-agent prompt

输入：
- target_file: 相对路径
- suggestions: suggestion 列表
- skills_dir: skills 根目录（绝对路径，sub-agent 用来 Read 原文件）
- change_output_dir: .change 文件输出目录（绝对路径，sub-agent 用来 Write）
- target_skill: optional

输出：4 字段 JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "prompts" / "evolver-prompt.md"
RULES_PATH = Path(__file__).resolve().parents[3] / "rules" / "evolver-agent-rules.md"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # infra/core/evolver/ → 项目根

_DEFAULT_SKILLS_DIR = Path("/home/10358563/.claude/agents/Skill-Evolution-Engine/skills")
_DEFAULT_CHANGE_OUTPUT_DIR = Path("/home/10358563/.claude/agents/Skill-Evolution-Engine/evidence/evolution_changes")

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _load_suggestions_from_reports(reports_dir: Path, target_file: str) -> list[dict]:
    if not reports_dir.is_dir():
        return []
    target_file = target_file.strip()
    matched = []
    for report_path in sorted(reports_dir.glob("*.analysis_report.json")):
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"WARN: {report_path.name} parse failed: {type(e).__name__}: {e}",
                  file=sys.stderr)
            continue
        for sg in data.get("suggestions", []):
            tf = (sg.get("target_file") or "").strip()
            if tf == target_file:
                clean_sg = {k: v for k, v in sg.items() if k not in ("target_skill", "target_file")}
                matched.append(clean_sg)
    return matched


def _sort_by_priority(suggestions: list[dict]) -> list[dict]:
    """
    **不过滤**所有 priority（high/medium/low 都保留），只排序。
    """
    return sorted(suggestions, key=lambda s: PRIORITY_ORDER.get(s.get("priority", "low"), 99))


def _flatten_target_file(target_file: str) -> str:
    """路径扁平化：skills/查询需求信息/SKILL.md → skills__查询需求信息__SKILL.md.change"""
    return target_file.replace("/", "__") + ".change"


def build_agent_call(
    target_file: str,
    suggestions: list[dict],
    skills_dir: Path,
    change_output_dir: Path,
    target_skill: str = "",
) -> dict:
    """构造 4 字段 JSON 配置。

    输入：
    - target_file: 相对路径（sub-agent 用此 Read 原文件）
    - suggestions: 已过滤+排序
    - skills_dir: 绝对路径（sub-agent 用此 Read）
    - change_output_dir: 绝对路径（sub-agent 用此 Write .change 文件）
    - target_skill: optional
    """
    target_file = target_file.strip()
    if not target_file:
        raise ValueError("target_file 不能为空")

    # 排序但不过滤（low 也保留——宝贵的经验）
    suggestions = _sort_by_priority(suggestions)

    # {{SUGGESTIONS_JSON}} 占位符填 suggestions（不含冗余字段）
    suggestions_payload = {"suggestions": suggestions}
    suggestions_json_str = json.dumps(suggestions_payload, ensure_ascii=False, indent=2)

    # .change 文件名（路径扁平化）
    change_filename = _flatten_target_file(target_file)

    # .change 文件完整路径——给 LLM 看用**相对路径**（简洁、跨机器可移植）
    # 工作目录 = Skill-Evolution-Engine 项目根，相对路径 = evidence/...
    try:
        change_output_dir_rel = change_output_dir.relative_to(_PROJECT_ROOT)
    except ValueError:
        # change_output_dir 不在项目根下（罕见），退化成绝对路径
        change_output_dir_rel = change_output_dir

    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    rules = RULES_PATH.read_text(encoding="utf-8")

    prompt = (template
              .replace("{{RULES}}", rules)
              .replace("{{TARGET_SKILL}}", target_skill)
              .replace("{{TARGET_FILE}}", target_file)
              .replace("{{SKILLS_DIR}}", str(skills_dir))
              .replace("{{CHANGE_OUTPUT_DIR}}", str(change_output_dir_rel))
              .replace("{{CHANGE_FILENAME}}", change_filename)
              .replace("{{SUGGESTIONS_JSON}}", suggestions_json_str))

    return {
        "description": f"Evolve {target_file} ({len(suggestions)} suggestions)",
        "subagent_type": "general-purpose",
        "run_in_background": True,
        "prompt": prompt,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="组装 evolver sub-agent prompt")
    parser.add_argument("target_file", help="target_file 相对路径")
    parser.add_argument("--skills-dir", type=Path, default=_DEFAULT_SKILLS_DIR)
    parser.add_argument("--change-output-dir", type=Path, default=_DEFAULT_CHANGE_OUTPUT_DIR,
                        help=".change 文件输出目录（默认 evidence/evolution_changes）")
    parser.add_argument("--reports-dir", type=Path,
                        default=Path("/home/10358563/.claude/agents/Skill-Evolution-Engine/evidence/analysis_reports"),
                        help="analysis_reports（fallback 用）")
    args = parser.parse_args()

    suggestions = _load_suggestions_from_reports(args.reports_dir, args.target_file)

    agent_call = build_agent_call(
        target_file=args.target_file,
        suggestions=suggestions,
        skills_dir=args.skills_dir.resolve(),
        change_output_dir=args.change_output_dir.resolve(),
    )

    summary = {
        "description": agent_call["description"],
        "subagent_type": agent_call["subagent_type"],
        "run_in_background": agent_call["run_in_background"],
        "prompt_length": len(agent_call["prompt"]),
        "placeholders_unfilled": sum(
            1 for p in ["{{RULES}}", "{{TARGET_SKILL}}", "{{TARGET_FILE}}",
                         "{{SKILLS_DIR}}", "{{CHANGE_OUTPUT_DIR}}", "{{CHANGE_FILENAME}}",
                         "{{SUGGESTIONS_JSON}}"]
            if p in agent_call["prompt"]
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())