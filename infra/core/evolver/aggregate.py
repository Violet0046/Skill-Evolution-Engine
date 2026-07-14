"""
aggregate.py — 按 target_file 聚合 suggestions

输出 schema：
{
  "reports_dir": "...",
  "target_files": [
    {
      "target_file": "...",
      "suggestions": [...]   # ← 内部 suggestion 不再含 target_skill / target_file（冗余）
    }
  ]
}

CLI：
    # Discovery 模式
    PYTHONPATH=infra python -m core.evolver.aggregate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_DEFAULT_REPORTS_DIR = Path("/home/10358563/.claude/agents/Skill-Evolution-Engine/evidence/analysis_reports")


def _load_reports(reports_dir: Path) -> list[dict]:
    if not reports_dir.is_dir():
        return []
    reports = []
    for report_path in sorted(reports_dir.glob("*.analysis_report.json")):
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            reports.append(data)
        except Exception as e:
            print(f"WARN: {report_path.name} parse failed: {type(e).__name__}: {e}",
                  file=sys.stderr)
    return reports


def aggregate_by_target_file(reports_dir: Path) -> list[dict]:
    """聚合 suggestions，按 target_file 分组。

    返回 list[dict]：
    [
      {
        "target_file": "<相对路径>",
        "suggestions": [<suggestion 对象，**已去掉 target_skill/target_file 冗余字段**>]
      }
    ]
    """
    reports = _load_reports(reports_dir)

    grouped: dict[str, list[dict]] = {}
    for data in reports:
        for sg in data.get("suggestions", []):
            tf = (sg.get("target_file") or "").strip()
            if not tf:
                continue
            # 移除冗余字段（target_skill / target_file 在 suggestion 内部和外壳重复）
            clean_sg = {k: v for k, v in sg.items() if k not in ("target_skill", "target_file")}
            grouped.setdefault(tf, []).append(clean_sg)

    return [
        {"target_file": tf, "suggestions": grouped[tf]}
        for tf in sorted(grouped.keys())
    ]


def get_suggestions_for_target(reports_dir: Path, target_file: str) -> list[dict]:
    """拿指定 target_file 的所有 suggestions（**保留 target_skill 字段**）。

    返回 raw suggestions（不过滤冗余字段）——调用方需要 target_skill 时用这个。
    """
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
                matched.append(sg)
    return matched


def get_clean_suggestions_for_target(reports_dir: Path, target_file: str) -> list[dict]:
    """拿指定 target_file 的所有 suggestions（**去掉冗余字段**）——build_agent_call 用。"""
    raw = get_suggestions_for_target(reports_dir, target_file)
    return [{k: v for k, v in sg.items() if k not in ("target_skill", "target_file")}
            for sg in raw]


def main() -> int:
    parser = argparse.ArgumentParser(description="discovery 模式：列出所有 target_file 的 suggestions")
    parser.add_argument("--reports-dir", type=Path, default=_DEFAULT_REPORTS_DIR,
                        help=f"analysis_reports 目录（默认 {_DEFAULT_REPORTS_DIR}）")
    args = parser.parse_args()

    entries = aggregate_by_target_file(args.reports_dir)
    result = {
        "reports_dir": str(args.reports_dir),
        "target_files_count": len(entries),
        "target_files": entries,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())