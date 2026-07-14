"""
evolve-discovery.py — 阶段 3 discovery 工具

**唯一职责**：列出有哪些 target_file 需要进化。

输出 JSON schema：
{
  "targets": [
    {"subject_name": "需求分析Agent", "target_file": "skills/.../SKILL.md"},
    {"subject_name": "需求分析Agent", "target_file": "agents/.../agent.md"},
    ...
  ]
}

主 agent 工作流：
    1. evolve-discovery.py → 拿 target_files[]
    2. for tf in target_files: see-evolve.py <tf>（循环）
    3. for call: Agent(**call)（循环）

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/evolve-discovery.py
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


DEFAULT_REPORTS_DIR = _ROOT / "evidence" / "analysis_reports"


def main() -> int:
    parser = argparse.ArgumentParser(description="阶段 3 discovery：列出所有 target_files")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR,
                        help=f"analysis_reports 目录（默认 {DEFAULT_REPORTS_DIR}）")
    args = parser.parse_args()

    from core.evolver.aggregate import aggregate_by_subject_target

    entries = aggregate_by_subject_target(args.reports_dir)
    result = {
        "targets": [
            {"subject_name": e["subject_name"], "target_file": e["target_file"]}
            for e in entries
        ]
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())