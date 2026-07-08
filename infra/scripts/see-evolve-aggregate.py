"""
see-evolve-aggregate.py — 阶段 3 工具 1：按 target_file 聚合 suggestions

扫描 `evidence/analysis_reports/*.analysis_report.json`，
按 `target_file` 聚合所有 suggestions（**跨 session 合并**），
输出 JSON 列表——每个 entry 是一个 unique target_file + 它的所有 suggestions。

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve-aggregate.py [<input_dir>]

stdout JSON schema：
{
  "status": "success",
  "input_dir": "<绝对路径>",
  "total_sessions": <int: 扫描到的 analysis_report 数>,
  "total_suggestions": <int: 全部 suggestions 总数（含 skipped）>,
  "skipped_no_target": <int: target_file 为空的 suggestion 数>,
  "target_files_count": <int: 唯一 target_file 数>,
  "target_files": [
    {
      "target_skill": "<从首条 suggestion 取>",
      "target_file": "<相对路径，如 skills/.../SKILL.md>",
      "suggestion_count": <int: 该 target_file 的 suggestion 数>,
      "suggestions": [<完整 suggestion 对象>, ...]
    },
    ...
  ]
}

status 含义：
- "success": 至少 1 个 analysis_report
- "error": 目录不存在 / 没有任何 analysis_report

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


DEFAULT_INPUT_DIR = _ROOT / "evidence" / "analysis_reports"


def aggregate_reports(input_dir: Path) -> dict:
    """扫描所有 *.analysis_report.json，按 target_file 聚合 suggestions。

    聚合规则：
    - 跨 session 合并：同一 target_file 的 suggestions 全并到一个 entry
    - 跳过 target_file 为空的 suggestion（analyzer 留空 = 不确定属于哪个 skill）
    - target_skill 取首条 suggestion 的值（同 target_file 通常一致；不一致时取首次出现的）
    - 输出按 target_file 字母序排序（稳定可测）
    """
    reports = sorted(input_dir.glob("*.analysis_report.json"))
    if not reports:
        return {
            "status": "error",
            "input_dir": str(input_dir),
            "error": f"no analysis_reports found in {input_dir}",
            "target_files": [],
        }

    # target_file -> {target_skill, suggestions[]}
    grouped: dict[str, dict] = {}
    total_suggestions = 0
    skipped_no_target = 0
    failed_reports: list[str] = []

    for report_path in reports:
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as e:
            failed_reports.append(f"{report_path.name}: {type(e).__name__}: {e}")
            continue

        for sg in data.get("suggestions", []):
            total_suggestions += 1
            tf = (sg.get("target_file") or "").strip()
            if not tf:
                # analyzer 留空 = 不确定属于哪个 skill，不进聚合
                skipped_no_target += 1
                continue

            if tf not in grouped:
                grouped[tf] = {
                    "target_skill": sg.get("target_skill", "") or "",
                    "target_file": tf,
                    "suggestions": [],
                }
            grouped[tf]["suggestions"].append(sg)

    target_files = []
    for tf in sorted(grouped.keys()):
        info = grouped[tf]
        target_files.append({
            "target_skill": info["target_skill"],
            "target_file": info["target_file"],
            "suggestion_count": len(info["suggestions"]),
            "suggestions": info["suggestions"],
        })

    result = {
        "status": "success",
        "input_dir": str(input_dir),
        "total_sessions": len(reports),
        "total_suggestions": total_suggestions,
        "skipped_no_target": skipped_no_target,
        "target_files_count": len(target_files),
        "target_files": target_files,
    }
    if failed_reports:
        result["failed_reports"] = failed_reports
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阶段 3 工具 1：聚合 analysis_reports，按 target_file 分组",
    )
    parser.add_argument("input_dir", nargs="?", default=str(DEFAULT_INPUT_DIR),
                        help=f"analysis_reports 目录（默认 {DEFAULT_INPUT_DIR}）")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="输出文件（默认 stdout）")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.is_dir():
        print(f"ERROR: 输入目录不存在: {input_dir}", file=sys.stderr)
        return 1

    result = aggregate_reports(input_dir)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已写入: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
