"""
see-evolve-finalize.py — 阶段 3 完成时调用 (主 agent 在所有 background sub-agent 完成之后)

职责:
1. 扫 evidence/<run_id>/evolution_changes/*.change
2. 读 .dispatch_stash.json (prompt_builder dispatch 时写的)
3. 拼出 (run_id, subject_target) -> {suggestions_json, original_content, new_content}
4. UPSERT 进 see_evolution_change

stdout 单 JSON: {"status": "success"|"error",
                 "run_id": "...",
                 "evolution_changes_recorded": N,
                 "flush_seconds": float}

退出码: 0 success, 1 配置缺失, 2 执行失败.

用法:
  PYTHONPATH=infra bash infra/scripts/with-python.sh \
      infra/scripts/see-evolve-finalize.py --run-id 2026-07-25-...
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阶段 3 完成: 把 .change 文件 + stash 一起入库 see_evolution_change",
    )
    parser.add_argument("--run-id", default=None, required=True,
                        help="本次 run_id (必填)")
    parser.add_argument("--evidence-root", type=Path,
                        default=_ROOT / "evidence",
                        help="默认 <project>/evidence")
    parser.add_argument("--flush-timeout", type=float, default=30.0,
                        help="等待 worker flush 队列的超时 (秒)")
    args = parser.parse_args()

    from core.review_db.config import ReviewDbConfig
    from core.review_db import get_client, flush as _flush, shutdown as _shutdown

    cfg = ReviewDbConfig.from_env()
    if cfg is None:
        out = {"status": "error", "error": "REVIEW_DB_HOST 未配置 (见 .env.example)"}
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    evidence_root: Path = args.evidence_root
    evolution_changes_dir = evidence_root / args.run_id / "evolution_changes"
    reports_dir = evidence_root / args.run_id / "analysis_reports"
    projects_home = Path(os.environ.get(  # noqa: F821  -- replaced below
        "SEE_PROJECTS_HOME", str(_ROOT / "subjects"),
    ))

    # 触发 client 启动 (start 后台 worker)
    client = get_client()
    if client is None:
        out = {"status": "error", "error": "review_db client 初始化失败 (disable / 配置)"}
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    t0 = time.time()
    evolution_changes_recorded = 0
    errors: list[dict] = []

    try:
        from core.review_db.hooks import scan_and_record_evolution_changes

        # 1) 阶段 3 产物: 扫 .change 文件
        if evolution_changes_dir.is_dir():
            try:
                evolution_changes_recorded = scan_and_record_evolution_changes(
                    run_id=args.run_id,
                    evidence_root=evidence_root,
                    evolution_changes_dir=evolution_changes_dir,
                    projects_home=projects_home,
                    # 给了 finalize 兜底重算 suggestions 的能力
                    reports_dir=reports_dir if reports_dir.is_dir() else None,
                )
            except Exception as e:
                errors.append({"stage": "scan_changes", "error": f"{type(e).__name__}: {e}"})

        # 注: 表 002 see_analysis_report 的入库已经在 evolve-discovery.py 完成,
        #     finalize 只负责表 004.

        # flush 队列 (让 worker 把入队的 sql 跑完)
        try:
            _flush(timeout=args.flush_timeout)
        except Exception as e:
            errors.append({"stage": "flush", "error": f"{type(e).__name__}: {e}"})

    finally:
        try:
            _shutdown(timeout=5.0)
        except Exception:
            pass

    elapsed = round(time.time() - t0, 3)
    if errors:
        out = {
            "status": "partial",
            "run_id": args.run_id,
            "evolution_changes_recorded": evolution_changes_recorded,
            "flush_seconds": elapsed,
            "errors": errors,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2), file=sys.stdout)
        return 2

    out = {
        "status": "success",
        "run_id": args.run_id,
        "evolution_changes_recorded": evolution_changes_recorded,
        "flush_seconds": elapsed,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    import os  # noqa: E402  -- 局部延迟 import 仅为 os.environ 一次性读取
    sys.exit(main())
