"""
aggregate.py — 按 target_file 聚合 suggestions

输出 schema：
{
  "reports_dir": "...",
  "targets": [
    {
      "subject_name": "...",
      "target_file": "...",
      "suggestions": [...]   # 内部 suggestion 已去掉 target_skill / target_file（冗余）
    }
  ]
}

CLI：
    # Discovery 模式
    PYTHONPATH=infra python3.8 -m core.evolver.aggregate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # infra/core/evolver/ → 项目根
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "evidence" / "analysis_reports"


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


def aggregate_by_subject_target(reports_dir: Path) -> list[dict]:
    """聚合 suggestions，按 (subject_name, target_file) 分组。

    subject_name 来自报告顶层字段（阶段 2 由脚本注入）——用它区分不同 agent
    工作流下**同名相对路径**的 target_file，否则会撞车覆盖。

    返回 list[dict]：
    [
      {
        "subject_name": "<报告顶层 subject_name>",
        "target_file": "<相对项目根的路径>",
        "suggestions": [<已去掉 target_skill/target_file 冗余字段>]
      }
    ]
    """
    reports = _load_reports(reports_dir)

    grouped: dict[tuple[str, str], list[dict]] = {}
    for data in reports:
        subject = (data.get("subject_name") or "").strip()
        for sg in data.get("suggestions", []):
            tf = (sg.get("target_file") or "").strip()
            if not tf:
                continue
            # 移除冗余字段（target_skill / target_file 在 suggestion 内部和外壳重复）
            clean_sg = {k: v for k, v in sg.items() if k not in ("target_skill", "target_file")}
            grouped.setdefault((subject, tf), []).append(clean_sg)

    return [
        {"subject_name": s, "target_file": tf, "suggestions": grouped[(s, tf)]}
        for (s, tf) in sorted(grouped.keys())
    ]


def get_suggestions_for_target(reports_dir: Path, target_file: str,
                               subject_name: str | None = None) -> list[dict]:
    """拿指定 (subject_name, target_file) 的所有 suggestions（**保留 target_skill 字段**）。

    subject_name 为 None 时不按 subject 过滤（向后兼容）；传值时只匹配报告顶层
    subject_name 相同的报告——避免跨 agent 工作流的同名路径混入。
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
        if subject_name is not None and (data.get("subject_name") or "").strip() != subject_name:
            continue
        for sg in data.get("suggestions", []):
            tf = (sg.get("target_file") or "").strip()
            if tf == target_file:
                matched.append(sg)
    return matched


def get_clean_suggestions_for_target(reports_dir: Path, target_file: str,
                                     subject_name: str | None = None) -> list[dict]:
    """拿指定 (subject_name, target_file) 的所有 suggestions（**去掉冗余字段**）——build_agent_call 用。"""
    raw = get_suggestions_for_target(reports_dir, target_file, subject_name)
    return [{k: v for k, v in sg.items() if k not in ("target_skill", "target_file")}
            for sg in raw]


def main() -> int:
    parser = argparse.ArgumentParser(description="discovery 模式：按 (subject_name, target_file) 列出 suggestions")
    parser.add_argument("--reports-dir", type=Path, default=_DEFAULT_REPORTS_DIR,
                        help=f"analysis_reports 目录（默认 {_DEFAULT_REPORTS_DIR}）")
    args = parser.parse_args()

    entries = aggregate_by_subject_target(args.reports_dir)
    result = {
        "reports_dir": str(args.reports_dir),
        "targets_count": len(entries),
        "targets": entries,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())