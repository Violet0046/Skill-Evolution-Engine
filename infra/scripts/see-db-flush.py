"""
see-db-flush.py — 开发用: 清空 review_db 5 张表

仅推荐本地调试使用. 真实环境下 production 数据永远不应用此.

stdout 单 JSON: {"status": "truncated"|"cancelled"|"error",
                 "tables": ["see_*", ...], "missing": [...]}

退出码: 0 success, 1 取消 / 配置缺失, 2 执行失败.

用法:
  # 跳过确认
  PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-db-flush.py --yes
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))


def main() -> int:
    parser = argparse.ArgumentParser(description="Truncate review_db tables (dev only).")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="跳过交互确认")
    parser.add_argument("--only", action="append", default=None,
                        help="仅清指定表 (例如 --only see_evidence --only see_run_session)")
    args = parser.parse_args()

    if not args.yes:
        print("ERROR: 需要 --yes 才能继续 (此操作不可逆)", file=sys.stderr)
        print("  e.g. PYTHONPATH=infra bash infra/scripts/with-python.sh \\",
              file=sys.stderr)
        print("         infra/scripts/see-db-flush.py --yes",
              file=sys.stderr)
        return 1

    from core.review_db.config import ReviewDbConfig

    cfg = ReviewDbConfig.from_env()
    if cfg is None:
        out = {"status": "error", "error": "REVIEW_DB_HOST 未配置"}
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    try:
        import pymysql
    except ImportError:
        out = {"status": "error", "error": "pymysql 未安装"}
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    targets = args.only or [
        "see_run_session",
        "see_analysis_report",
        "see_evidence",
        "see_evolution_change",
        "see_review_decision",
    ]

    try:
        conn = pymysql.connect(
            host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password,
            database=cfg.database, charset="utf8mb4", autocommit=True,
        )
    except Exception as e:
        out = {"status": "error", "error": f"连接失败: {type(e).__name__}: {e}"}
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    truncated: list[str] = []
    missing: list[str] = []
    errors: list[dict] = []

    try:
        with conn.cursor() as cur:
            # 检查实际存在的表
            cur.execute("SHOW TABLES")
            existing = {r[0] for r in cur.fetchall()}
            for t in targets:
                if t not in existing:
                    missing.append(t)
                    continue
                try:
                    cur.execute(f"TRUNCATE TABLE `{t}`")
                    truncated.append(t)
                except Exception as e:
                    errors.append({"table": t, "error": f"{type(e).__name__}: {e}"})
    finally:
        conn.close()

    status = "truncated" if not errors and not missing else (
        "partial" if truncated or errors else "error"
    )
    code = 0 if status == "truncated" else 2

    out = {
        "status": status,
        "tables": truncated,
        "missing": missing,
        "errors": errors,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2), file=sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
