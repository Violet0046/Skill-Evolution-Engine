"""
review_db.schema — SQL 片段 + JSON 规范化工具

4 张表的 UPSERT SQL (MySQL 8) + 字符串格式化辅助.

注: 见 ddl/*.sql 知唯一键 (UK) 命名 -- INSERT ... ON DUPLICATE KEY UPDATE
针对每个 UK 触发, 等价 UPSERT.
"""
from __future__ import annotations

from typing import Tuple

# Subject_target = '<subject_name>@<target_file>'
SUBJECT_TARGET_SEP = "@"

# 表 002 / 004 列宽: utf8mb4 + 复合主键字节上限 (3072) 推算
#  - 002 uk  = (run_id VARCHAR(64), session_id VARCHAR(64), subject_target) → 上限 ~600
#  - 004 uk  = (run_id VARCHAR(64), subject_target)                              → 上限 ~700
SUBJECT_TARGET_MAX_LEN_TABLE_002 = 600
SUBJECT_TARGET_MAX_LEN_TABLE_004 = 700


def normalize_subject_target(subject_name: str, target_file: str) -> str:
    """subject + target 用 '@' 拼接 (DDL 002/004 业务键要求)."""
    if SUBJECT_TARGET_SEP in (subject_name or ""):
        raise ValueError(
            f"subject_name contains forbidden '{SUBJECT_TARGET_SEP}': {subject_name!r}"
        )
    out = f"{subject_name}{SUBJECT_TARGET_SEP}{target_file}"
    # 默认检查最严苛的限制 (002 表); 调用方知道在用哪张表时可放宽
    if len(out) > SUBJECT_TARGET_MAX_LEN_TABLE_002:
        raise ValueError(
            f"subject_target too long ({len(out)} > "
            f"{SUBJECT_TARGET_MAX_LEN_TABLE_002}): {out[:80]!r}..."
        )
    return out


def split_subject_target(subject_target: str) -> Tuple[str, str]:
    """反向: subject_target -> (subject_name, target_file).

    注意 target_file 可能含 '@' (罕见, 但路径层理论可能), 这里只切首个 '@'.
    """
    if SUBJECT_TARGET_SEP not in subject_target:
        raise ValueError(f"not a valid subject_target: {subject_target!r}")
    name, _, target = subject_target.partition(SUBJECT_TARGET_SEP)
    return name, target


def flatten_change_filename(subject_name: str, target_file: str) -> str:
    """与 infra/core/evolver/prompt_builder.py:_flatten_target_file 相同的规则.

    保留该函数以便测试 + 反向解析时验证一致性.
    """
    key = f"{subject_name}/{target_file}" if subject_name else target_file
    return key.replace("/", "__") + ".change"


def parse_change_filename(filename: str) -> Tuple[str, str]:
    """反向: 'foo__agents__bar__baz.md.change' -> (foo, agents/bar/baz.md).

    需要外部传 subject_name 来切 (因为保留 subject_name 与 target_file 边界),
    此函数只把 '__' 还原为 '/'.
    """
    if not filename.endswith(".change"):
        raise ValueError(f"not a .change filename: {filename!r}")
    base = filename[: -len(".change")]
    # 不能单靠 __ 反推 subject_name/target_file 边界 — 留给上层调用方提供
    # subject_name 切片位置时用, 此处不做切分, 仅返回 (None, restored_path).
    return "", base.replace("__", "/")


# ------------------------------------------------------------
# UPSERT SQL: 参数化 (所有 % 占位符由 PyMySQL 通过 %s 提交)
# ------------------------------------------------------------

# 表 001 see_run_session (UK: (run_id, session_id))
UPSERT_RUN_SESSION_SQL = """
INSERT INTO see_run_session
    (run_id, session_id, agent_cwd, by_agent_type, summary, index_raw)
VALUES (%s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    agent_cwd     = VALUES(agent_cwd),
    by_agent_type = VALUES(by_agent_type),
    summary       = VALUES(summary),
    index_raw     = VALUES(index_raw)
""".strip()

# 表 002 see_analysis_report (UK: (run_id, session_id, subject_target))
UPSERT_ANALYSIS_REPORT_SQL = """
INSERT INTO see_analysis_report
    (run_id, session_id, subject_target, suggestions_json)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    suggestions_json = VALUES(suggestions_json)
""".strip()

# 表 003 see_evidence (UK: (session_id, uuid))
UPSERT_EVIDENCE_SQL = """
INSERT INTO see_evidence (session_id, uuid, detail_json)
VALUES (%s, %s, %s)
ON DUPLICATE KEY UPDATE
    detail_json = VALUES(detail_json)
""".strip()

# 表 004 see_evolution_change (UK: (run_id, subject_target))
UPSERT_EVOLUTION_CHANGE_SQL = """
INSERT INTO see_evolution_change
    (run_id, subject_target, original_content, new_content, suggestions_json)
VALUES (%s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    original_content  = VALUES(original_content),
    new_content       = VALUES(new_content),
    suggestions_json  = VALUES(suggestions_json)
""".strip()

# 表 004 "种子" 写入: 阶段 3 evolve-discovery 时机调用, 先占位 (subject_target+suggestions_json),
# original_content/new_content 留空, finalize 阶段再覆盖.
# 不同记录点, **不同** SQL, 让 review 系统早期可见该 target.
UPSERT_EVOLUTION_CHANGE_SEEDED_SQL = """
INSERT INTO see_evolution_change
    (run_id, subject_target, original_content, new_content, suggestions_json)
VALUES (%s, %s, %s, '', %s)
ON DUPLICATE KEY UPDATE
    suggestions_json  = VALUES(suggestions_json)
""".strip()


# ------------------------------------------------------------
# ddl/ 目录里的 5 张表清单 (用于 see-migrate.py 顺序执行)
# ------------------------------------------------------------
DDL_FILES_ORDER = [
    "001_see_run_session.sql",
    "002_see_analysis_report.sql",
    "003_see_evidence.sql",
    "004_see_evolution_change.sql",
    "005_see_review_decision.sql",
]
