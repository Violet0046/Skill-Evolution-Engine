"""build_arch.py —— 从 subjects/ 下扫描每个 Agent 的 agents/skills/rules，
生成极简版 agent-architectures/<name>.json（人维护用，不进主工作流）。

Schema:
{
  "agent_name": "<subject name>",
  "agents": [{"name", "path", "description"}, ...],
  "skills": [{"name", "path", "description"}, ...],
  "rules":  [{"name", "path", "description"}, ...]
}

默认路径（相对脚本所在项目根）：
  subjects/                  → 输入目录
  agent-architectures/       → 输出目录

用法：
    python3 infra/core/util/build_arch.py
    python3 infra/core/util/build_arch.py --subjects /path/to/subjects --out /path/to/agent-architectures
    python3 infra/core/util/build_arch.py --subject 需求分析Agent
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 项目根 = scripts 所在目录的爷爷级
# infra/core/util/build_arch.py → 项目根
_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SUBJECTS = _ROOT / "subjects"
DEFAULT_OUT = _ROOT / "agent-architectures"


def parse_frontmatter(text: str) -> dict:
    """极简 frontmatter 解析：只认首段 --- ... ---。"""
    if not text.startswith("---"):
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm


def rule_scope(name: str) -> str:
    if "全局" in name:
        return "全局"
    if "阶段" in name:
        return "阶段"
    if "回退" in name:
        return "回退"
    return "其他"


def build_subject_arch(subject_name: str, subject_root: Path) -> dict:
    agents: list = []
    skills: list = []
    rules: list = []

    # agents/
    agents_dir = subject_root / "agents"
    if agents_dir.is_dir():
        for entry in sorted(agents_dir.iterdir()):
            if not entry.is_dir():
                continue
            md_files = [p for p in entry.iterdir() if p.suffix == ".md"]
            if not md_files:
                continue
            md = md_files[0]
            fm = parse_frontmatter(md.read_text(encoding="utf-8"))
            agents.append({
                "name": fm.get("name", entry.name),
                "path": f"agents/{entry.name}/{md.name}",
                "description": fm.get("description", ""),
            })

    # skills/
    skills_dir = subject_root / "skills"
    if skills_dir.is_dir():
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue
            fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            skills.append({
                "name": fm.get("name", entry.name),
                "path": f"skills/{entry.name}/SKILL.md",
                "description": fm.get("description", ""),
            })

    # rules/
    rules_dir = subject_root / "rules"
    if rules_dir.is_dir():
        for md in sorted(rules_dir.iterdir()):
            if not md.is_file() or md.suffix != ".md":
                continue
            name = md.stem
            rules.append({
                "name": name,
                "path": f"rules/{md.name}",
                "description": f"{rule_scope(name)}规则",
            })

    return {
        "agent_name": subject_name,
        "agents": agents,
        "skills": skills,
        "rules": rules,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从 subjects/ 扫描生成 agent-architectures/<name>.json（人维护用）",
    )
    parser.add_argument(
        "--subjects", type=Path, default=DEFAULT_SUBJECTS,
        help=f"subjects 根目录（默认 {DEFAULT_SUBJECTS}）",
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT,
        help=f"agent-architectures 输出目录（默认 {DEFAULT_OUT}）",
    )
    parser.add_argument(
        "--subject", action="append", default=None,
        help="只处理指定 subject（可多次传），默认处理全部",
    )
    args = parser.parse_args()

    if not args.subjects.is_dir():
        print(f"ERROR: subjects 目录不存在: {args.subjects}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)

    targets = sorted(d.name for d in args.subjects.iterdir() if d.is_dir())
    if args.subject:
        targets = [t for t in targets if t in args.subject]
        missing = set(args.subject) - set(targets)
        if missing:
            print(f"WARN: 以下 subject 在 {args.subjects} 下找不到: {sorted(missing)}", file=sys.stderr)

    for name in targets:
        arch = build_subject_arch(name, args.subjects / name)
        out_path = args.out / f"{name}.json"
        out_path.write_text(
            json.dumps(arch, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"[OK] {out_path.name}  "
            f"agents={len(arch['agents'])}  "
            f"skills={len(arch['skills'])}  "
            f"rules={len(arch['rules'])}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())