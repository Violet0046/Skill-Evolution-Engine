"""
see-evolve.py — 阶段 3 入口（**per-target_file 4 字段 JSON 输出**）

仿照 see-analyze.py 的 data-driven dispatch 模式：
- 输入：单个 target_file（如 `skills/查询需求信息/SKILL.md`）
- 内部：从所有 analysis_reports 聚合该 target_file 的 suggestions
- 输出：4 字段 JSON（description / subagent_type / run_in_background / prompt）

主 agent 拿到这个 JSON 后**逐个** fire Agent()（逐个 dispatch + run_in_background
= 上下文安全 + 保留 sub-agent 后台并发）。

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <target_file> [--skills-dir <path>] [--evolved-skills-dir <path>] [--reports-dir <path>]

参数：
- `<target_file>`：必填，target_file 相对路径
- `--skills-dir`：目标文件所在目录（绝对路径），默认 `<项目根>/skills`
- `--evolved-skills-dir`：patch 失败回退时的副本目录（绝对路径），默认 `<项目根>/evolved_skills`
- `--reports-dir`：analysis_reports 目录（绝对路径），默认 `<项目根>/evidence/analysis_reports`
- `--output`：JSON 输出文件（默认 stdout）

退出码：0 = success，1 = error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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


_ROOT = Path(__file__).resolve().parents[2]
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))


PROMPT_TEMPLATE_PATH = _ROOT / "prompts" / "evolver-prompt.md"
RULES_PATH = _ROOT / "rules" / "evolver-agent-rules.md"
DEFAULT_REPORTS_DIR = _ROOT / "evidence" / "analysis_reports"
DEFAULT_SKILLS_DIR = _ROOT / "skills"
DEFAULT_EVOLVED_SKILLS_DIR = _ROOT / "evolved_skills"

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _load_suggestions_for_target(reports_dir: Path, target_file: str) -> list[dict]:
    """从所有 analysis_reports 拿这个 target_file 的所有 suggestions。

    跨 session 聚合（同一个 target_file 可能出现在多份 report 中）。
    不过滤 priority——过滤由调用方决定。
    """
    target_file = target_file.strip()
    if not target_file:
        return []

    if not reports_dir.is_dir():
        return []

    matched: list[dict] = []
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
                matched.append(sg)

    return matched


def _filter_and_sort_suggestions(suggestions: list[dict]) -> list[dict]:
    """过滤掉 low 优先级，按 high > medium 排序。

    v1 跳过 low（low 通常是 nice-to-have，不该自动 patch）。
    """
    filtered = [s for s in suggestions if s.get("priority") in ("high", "medium")]
    filtered.sort(key=lambda s: PRIORITY_ORDER.get(s.get("priority", "low"), 99))
    return filtered


def build_agent_call(
    target_file: str,
    skills_dir: Path,
    evolved_skills_dir: Path,
    reports_dir: Path,
) -> dict:
    """构造 per-target_file 的 4 字段 JSON 配置（data-driven dispatch）。

    主 agent 拿这个 JSON 直接当 Agent(...) 调用的参数源——
    避免主 agent 自己选错 subagent_type、忘加 run_in_background、或手写 prompt。

    4 个字段：
    - description: Agent tool 必填
    - subagent_type: 硬编码 "general-purpose"
    - run_in_background: 硬编码 True
    - prompt: 完整的 evolver-prompt（已替换所有占位符）
    """
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    rules = RULES_PATH.read_text(encoding="utf-8")

    suggestions = _load_suggestions_for_target(reports_dir, target_file)
    suggestions = _filter_and_sort_suggestions(suggestions)

    # target_skill：取首条 suggestion 的值（同 target_file 通常一致）
    target_skill = (suggestions[0].get("target_skill") or "") if suggestions else ""

    # suggestions 数量为 0 时的 placeholder（让 sub-agent 不必处理空数组）
    suggestions_json_str = (
        json.dumps(suggestions, ensure_ascii=False, indent=2)
        if suggestions
        else "[]  // 注：此 target_file 下没有 high/medium 优先级 suggestions，sub-agent 直接输出 <EVOLUTION_COMPLETE> 并标 total_suggestions: 0 即可"
    )

    prompt = (template
              .replace("{{RULES}}", rules)
              .replace("{{TARGET_SKILL}}", target_skill)
              .replace("{{TARGET_FILE}}", target_file)
              .replace("{{SKILLS_DIR}}", str(skills_dir))
              .replace("{{EVOLVED_SKILLS_DIR}}", str(evolved_skills_dir))
              .replace("{{SUGGESTIONS_JSON}}", suggestions_json_str))

    return {
        "description": f"Evolve {target_file} ({len(suggestions)} suggestions)",
        "subagent_type": "general-purpose",
        "run_in_background": True,
        "prompt": prompt,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阶段 3 入口：构造 per-target_file 的 4 字段 JSON 配置（data-driven dispatch）",
    )
    parser.add_argument("target_file",
                        help="目标文件相对路径（如 skills/查询需求信息/SKILL.md）")
    parser.add_argument("--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR,
                        help=f"目标文件所在目录（默认 {DEFAULT_SKILLS_DIR}）")
    parser.add_argument("--evolved-skills-dir", type=Path, default=DEFAULT_EVOLVED_SKILLS_DIR,
                        help=f"patch 失败回退时的副本目录（默认 {DEFAULT_EVOLVED_SKILLS_DIR}）")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR,
                        help=f"analysis_reports 目录（默认 {DEFAULT_REPORTS_DIR}）")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="JSON 输出文件（默认 stdout）")
    args = parser.parse_args()

    agent_call = build_agent_call(
        target_file=args.target_file,
        skills_dir=args.skills_dir.resolve(),
        evolved_skills_dir=args.evolved_skills_dir.resolve(),
        reports_dir=args.reports_dir.resolve(),
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(agent_call, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已写入: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(agent_call, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
