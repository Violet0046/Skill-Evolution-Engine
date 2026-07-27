"""
backend/app/db/queries.py — 5 张表的 SQL 字符串 + 原始查询辅助

所有查询函数返回原始 dict (SQLAlchemy mappings), 由调用方 (api/*.py) 转 pydantic.
模式: text() + db.execute() + mappings().

JSON 列防御: PyMySQL 1.x 默认会把 MySQL JSON 列解析为 dict/list (Python 类型).
少数版本 / 驱动配置可能返 str — 防御性 json.loads() 在 _normalize_json_field() 工具里.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _normalize_json_field(value: Any) -> Any:
    """把 JSON 列的值归一化为 Python 对象.

    PyMySQL 大多数情况下把 MySQL JSON 列解析为 dict/list. 万一是 str (例如 sql_mode 严格),
    兜底 json.loads. None 透传.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value   # parse 失败保持原值让上层排查
    return value   # 其它 (int, bool) 保持


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """datetime → ISO8601 string."""
    return dt.isoformat() if isinstance(dt, datetime) else None


# ------------------------------------------------------------
# see_evolution_change
# ------------------------------------------------------------

def list_changes_for_run(
    db: Session, run_id: str, limit: int = 50, offset: int = 0
) -> List[Dict[str, Any]]:
    """按 run_id 列出 changes (含评审事件聚合).

    SQL 关键:
      - LEFT JOIN see_review_decision: 即使没人评审, 也返 0/0/0 (COALESCE NULL → 0)
      - GROUP BY c.id: 让 SUM 只对每个 change 聚合
      - 把字段 (suggestions_count 等) 用函数表达式, 这样不用读 200KB 完整 content
    """
    sql = text("""
        SELECT
            c.id,
            c.run_id,
            c.subject_target,
            LENGTH(c.original_content) AS original_length,
            LENGTH(c.new_content)      AS new_length,
            JSON_LENGTH(c.suggestions_json) AS suggestions_count,
            COALESCE(SUM(CASE WHEN d.decision = 'approved' THEN 1 ELSE 0 END), 0)
                AS decision_count_approved,
            COALESCE(SUM(CASE WHEN d.decision = 'modified' THEN 1 ELSE 0 END), 0)
                AS decision_count_modified,
            COALESCE(SUM(CASE WHEN d.decision = 'rejected' THEN 1 ELSE 0 END), 0)
                AS decision_count_rejected
        FROM see_evolution_change c
        LEFT JOIN see_review_decision d
               ON d.evolution_change_id = c.id
        WHERE c.run_id = :run_id
        GROUP BY c.id, c.run_id, c.subject_target
        ORDER BY c.subject_target
        LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(
        sql, {"run_id": run_id, "limit": limit, "offset": offset}
    ).mappings().all()
    return [dict(r) for r in rows]


def list_runs(db: Session) -> List[str]:
    """返回所有出现过的 run_id (去重, 倒序 — 最新在前).

    SELECT DISTINCT run_id FROM see_evolution_change ORDER BY run_id DESC
    """
    sql = text("""
        SELECT DISTINCT run_id
        FROM see_evolution_change
        ORDER BY run_id DESC
    """)
    rows = db.execute(sql).scalars().all()
    return list(rows)


def get_change_by_id(db: Session, change_id: int) -> Optional[Dict[str, Any]]:
    """单个 change 详情. 返回 None 当没找到."""
    sql = text("""
        SELECT id, run_id, subject_target,
               original_content, new_content, suggestions_json, linediff_json
        FROM see_evolution_change
        WHERE id = :id
    """)
    row = db.execute(sql, {"id": change_id}).mappings().first()
    if row is None:
        return None
    out = dict(row)
    out["suggestions_json"] = _normalize_json_field(out.get("suggestions_json")) or []
    out["linediff"] = _normalize_json_field(out.get("linediff_json"))
    out.pop("linediff_json", None)  # 不暴露内部列名
    return out


# ------------------------------------------------------------
# see_evidence
# ------------------------------------------------------------

def get_evidence(
    db: Session, session_id: str, uuid: str
) -> Optional[Dict[str, Any]]:
    """UK (session_id, uuid). 返回 None 当没找到."""
    sql = text("""
        SELECT session_id, uuid, detail_json
        FROM see_evidence
        WHERE session_id = :session_id AND uuid = :uuid
    """)
    row = db.execute(
        sql, {"session_id": session_id, "uuid": uuid}
    ).mappings().first()
    if row is None:
        return None
    out = dict(row)
    out["detail_json"] = _normalize_json_field(out.get("detail_json")) or {}
    return out


# ------------------------------------------------------------
# see_review_decision
# ------------------------------------------------------------

def insert_decision(
    db: Session,
    change_id: int,
    decision: str,
    reviewer: str,
    comment: Optional[str] = None,
    modified_content: Optional[str] = None,
) -> Dict[str, Any]:
    """插入一条评审决策, 同时返回刚插入的 (id, decision, reviewer, reviewed_at).

    实现策略:
      - INSERT 用 NOW(3) 让数据库统一时间源 (避免 python 时区漂移)
      - INSERT 完后用 cursor.lastrowid + 一次 SELECT 拿 reviewed_at
      - 两步在同一个 db transaction 内 (commit 由 FastAPI Depends 控制 — 我们
        在这里 commit, 因为这是 route handler 唯一写动作)
    """
    insert_sql = text("""
        INSERT INTO see_review_decision
            (evolution_change_id, decision, comment, modified_content, reviewer, reviewed_at)
        VALUES
            (:evolution_change_id, :decision, :comment, :modified_content, :reviewer, NOW(3))
    """)
    result = db.execute(insert_sql, {
        "evolution_change_id": change_id,
        "decision": decision,
        "comment": comment,
        "modified_content": modified_content,
        "reviewer": reviewer,
    })
    new_id = result.lastrowid
    db.commit()

    # 再查一次拿 reviewed_at (MySQL 没 RETURNING)
    select_sql = text("""
        SELECT id, decision, reviewer, reviewed_at
        FROM see_review_decision
        WHERE id = :id
    """)
    row = db.execute(select_sql, {"id": new_id}).mappings().first()
    if row is None:
        # 极端情况: 并发删除或失败. 返我们知道的.
        return {
            "id": new_id,
            "decision": decision,
            "reviewer": reviewer,
            "reviewed_at": None,
        }
    out = dict(row)
    out["reviewed_at"] = _iso(out["reviewed_at"])
    return out
