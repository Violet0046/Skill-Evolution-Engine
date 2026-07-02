"""see-evolve.py — 阶段 3 入口（输入校验 + bundle 组装）

设计同 see-analyze.py：
- 不在 CLI 内调 LLM
- 职责：
  1. 校验 analysis_report.json 存在且可解析
  2. 校验 skills_dir（可选）
  3. 输出 evolver_bundle（report 路径 + skills_dir + skill_search_paths + summary + prompt 路径）
- **不读 prompt 模板**：主 agent 自己 Read `prompts/evolver-prompt.md`

用法：
    PYTHONPATH=infra python infra/scripts/see-evolve.py <analysis_report.json> [skills_dir] \
        [--evolved-skills-dir <dir>] [--output <bundle.json>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

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


def _load_report(report_path: Path) -> Dict[str, Any]:
    return json.loads(report_path.read_text(encoding="utf-8"))


def _summarize_suggestions(report: Dict[str, Any]) -> Dict[str, Any]:
    suggestions = report.get("suggestions", [])
    return {
        "total": len(suggestions),
        "by_priority": {
            "high": sum(1 for s in suggestions if s.get("priority") == "high"),
            "medium": sum(1 for s in suggestions if s.get("priority") == "medium"),
            "low": sum(1 for s in suggestions if s.get("priority") == "low"),
        },
        "target_skills": sorted({s.get("target_skill", "") for s in suggestions if s.get("target_skill")}),
    }


def build_bundle(report_path: Path, skills_dir: Optional[Path], evolved_skills_dir: Optional[Path]) -> Dict[str, Any]:
    """构造 evolver_bundle。不再读 prompt 模板——主 agent 自己 Read。"""
    if not report_path.exists():
        return {
            "report_path": str(report_path),
            "skills_dir": str(skills_dir) if skills_dir else None,
            "ready": False,
            "error": f"analysis_report.json 不存在: {report_path}",
        }
    if skills_dir is not None and not skills_dir.is_dir():
        return {
            "report_path": str(report_path),
            "skills_dir": str(skills_dir),
            "ready": False,
            "error": f"skills_dir 不是目录: {skills_dir}",
        }

    report = _load_report(report_path)
    summary = _summarize_suggestions(report)

    # 默认 evolved_skills_dir 位置
    if evolved_skills_dir is None:
        if skills_dir is not None:
            evolved_skills_dir = skills_dir.parent / "evolved_skills"
        else:
            _root = Path(__file__).resolve().parents[2]
            evolved_skills_dir = _root / "evolved_skills"

    return {
        "report_path": str(report_path),
        "skills_dir": str(skills_dir) if skills_dir else None,
        "evolved_skills_dir": str(evolved_skills_dir),
        "ready": True,
        "summary": summary,
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
        "skill_search_paths": [
            "$CWD/.claude/skills/",
            "$CWD/.claude/skills/*/",
            "$CWD/.claude/agents/*/skills/",
            "$CWD/.claude/agents/*/.claude/skills/",
            "$CWD/.claude/agents/*/",
            "$CWD/skills/",
            "$HOME/.claude/skills/",
            "$HOME/.claude/agents/*/skills/",
            "$HOME/.claude/agents/*/.claude/skills/",
            "$HOME/.claude/agents/*/",
        ],
        "context": {
            "session_id": report.get("session_id"),
            "suggestions": report.get("suggestions", []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阶段 3 入口：准备 evolver agent 的 prompt + 输入校验",
    )
    parser.add_argument("report", type=Path, help="analysis_report.json 路径")
    parser.add_argument("skills_dir", type=Path, nargs="?", default=None,
                        help="被进化的 skill/subagent 源目录（可选；不传时 evolver 用 bundle.skill_search_paths 自动探测）")
    parser.add_argument("--evolved-skills-dir", type=Path, default=None,
                        help="进化后副本目录（默认 <skills_dir>/../evolved_skills 或 <项目根>/evolved_skills）")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="bundle 输出文件（默认 stdout）")
    args = parser.parse_args()

    bundle = build_bundle(args.report, args.skills_dir, args.evolved_skills_dir)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已写入 bundle: {args.output}")
    else:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))

    return 0 if bundle.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main())
