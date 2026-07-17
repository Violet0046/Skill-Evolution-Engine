"""
evolve-discovery.py — 阶段 3 discovery 工具

**唯一职责**：列出本次 run 的 analysis_reports 下有哪些 target_file 需要进化。

输出 JSON schema：
{
  "run_id": "<本次 run>",
  "targets": [
    {"subject_name": "需求分析Agent", "target_file": "skills/.../SKILL.md"},
    {"subject_name": "需求分析Agent", "target_file": "agents/.../agent.md"},
    ...
  ]
}

主 agent 工作流：
    1. evolve-discovery.py --run-id <id> → 拿 targets[]
    2. for t in targets: see-evolve.py <subject_name> <target_file> --run-id <id>（循环）
    3. for call: Agent(**call)（循环）

run_id 隔离：从 evidence/<run_id>/analysis_reports/ 聚合。
--run-id 必填——不传直接报错，不做 env fallback / 时间戳 fallback。

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/evolve-discovery.py --run-id <id>
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


def main() -> int:
    parser = argparse.ArgumentParser(description="阶段 3 discovery：列出本次 run 的 target_files")
    parser.add_argument("--run-id", default=None,
                        help="本次运行 run_id（必填，从阶段 1 stdout 解析得到）")
    parser.add_argument("--reports-dir", type=Path, default=None,
                        help="analysis_reports 目录（默认 evidence/<run_id>/analysis_reports/）")
    args = parser.parse_args()

    if not args.run_id:
        print("ERROR: --run-id 必填（从阶段 1 stdout 的 run_id 字段解析得到）", file=sys.stderr)
        return 2
    reports_dir = args.reports_dir or (_ROOT / "evidence" / args.run_id / "analysis_reports")

    from core.evolver.aggregate import aggregate_by_subject_target

    entries = aggregate_by_subject_target(reports_dir)
    result = {
        "run_id": args.run_id,
        "targets": [
            {"subject_name": e["subject_name"], "target_file": e["target_file"]}
            for e in entries
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())