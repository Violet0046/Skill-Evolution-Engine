"""
see-migrate.py — 把 infra/core/review_db/ddl/*.sql 顺序执行到 MySQL.

幂等: 所有 DDL 已写 "IF NOT EXISTS"; 重复执行不会破坏现有表.

stdout 单 JSON: {"status": "success"|"error", "tables_created": [...],
                 "tables_existing": [...], "executed_files": [...]}

退出码: 0 成功, 1 配置缺失 / 连接失败, 2 部分表 DDL 执行失败.

用法:
  # 配置见 infra/core/review_db/.env.example
  PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-migrate.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 与项目其他 see-*.py 一致: 直接注入 infra 到 sys.path,
# 兼容直接 `python see-migrate.py` 与 `with-python.sh <with PYTHONPATH=infra>` 两种入口
_ROOT = Path(__file__).resolve().parents[2]            # .../Skill-Evolution-Engine
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply review_db DDL to MySQL (idempotent).")
    parser.add_argument(
        "--ddl-dir",
        type=Path,
        default=_ROOT / "infra" / "core" / "review_db" / "ddl",
        help="DDL 目录 (默认: infra/core/review_db/ddl)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        help="只执行指定前缀的 DDL (例如 --only 001 --only 003); 默认全部",
    )
    args = parser.parse_args()

    from core.review_db.config import ReviewDbConfig

    cfg = ReviewDbConfig.from_env()
    if cfg is None:
        out = {
            "status": "error",
            "error": "REVIEW_DB_HOST 未配置 (.env 或 env). 见 infra/core/review_db/.env.example",
        }
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    try:
        import pymysql
    except ImportError:
        out = {"status": "error", "error": "pymysql 未安装, 见 requirements.txt"}
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    if not args.ddl_dir.is_dir():
        out = {"status": "error", "error": f"DDL 目录不存在: {args.ddl_dir}"}
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    # 决定要执行哪些文件
    files = sorted(p for p in args.ddl_dir.glob("*.sql") if p.is_file())
    if args.only:
        prefixes = tuple(args.only)
        files = [p for p in files if p.name.startswith(prefixes)]
    if not files:
        out = {"status": "error", "error": f"未匹配到 DDL 文件 (--only={args.only})"}
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    try:
        conn = pymysql.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database=cfg.database,
            charset="utf8mb4",
            autocommit=True,
        )
    except Exception as e:
        out = {
            "status": "error",
            "error": f"MySQL 连接失败: {type(e).__name__}: {e}",
        }
        print(json.dumps(out, ensure_ascii=False), file=sys.stdout)
        return 1

    executed: list[str] = []
    created: list[str] = []
    existing: list[str] = []
    failures: list[dict] = []

    try:
        with conn.cursor() as cur:
            for fp in files:
                sql = fp.read_text(encoding="utf-8")
                # 拆 statements (PyMySQL 默认不支持 multi-statement, 需 client_flag)
                # 这里我们就一次跑完整个文件. DDL 文件本身都加 IF NOT EXISTS + 单表,
                # 多文件单 SQL 的简单结构即可正常工作. 若以后碰上 multi-statement
                # 的 ddl, 可改用 conn.set_sql_options 或加 CLIENT.MULTI_STATEMENTS.
                try:
                    cur.execute(sql)
                    executed.append(fp.name)
                    # 推断刚才是 CREATE 还是 已存在的: 通过 SHOW TABLES LIKE
                    # (这里简化: 全部计入 executed, 不区分 created/existing —
                    #  一律走 IF NOT EXISTS 路径, 该列退化)
                    # 若需要区分, 在每个 DDL 文件末尾用 INSERT IGNORE INTO ... VALUES ...
                    # 元数据表, 或在 worker 里做 SELECT table_name FROM information_schema.
                except Exception as e:
                    failures.append({"file": fp.name, "error": f"{type(e).__name__}: {e}"})
    finally:
        conn.close()

    if failures:
        out = {
            "status": "error",
            "executed_files": executed,
            "failures": failures,
            "tables_created": created,
            "tables_existing": existing,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2), file=sys.stdout)
        return 2

    # 全部成功后, 重写一次 SHOW TABLES 用于 self-check 输出
    try:
        import pymysql as _p  # noqa: F401
        conn2 = _p.connect(
            host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password,
            database=cfg.database, charset="utf8mb4", autocommit=True,
        )
        with conn2.cursor() as cur:
            cur.execute("SHOW TABLES")
            tables = [r[0] for r in cur.fetchall()]
        conn2.close()
    except Exception:
        tables = []

    out = {
        "status": "success",
        "executed_files": executed,
        "tables_now": tables,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2), file=sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
