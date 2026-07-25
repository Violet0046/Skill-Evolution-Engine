"""
review_db.hooks — 高层钩子函数

对源码调用方 (failure_detail.py, index_store.py, see-*.py) 屏蔽 DB 细节.
所有钩子的契约:
  - 即时返回, 绝不抛出
  - 配置缺失 / REVIEW_DB_DISABLED 时自动 no-op
  - DB 写失败时仅 warn / debug, 不影响流水线

尽量从入参构造所有数据 (不直接操作 schema / client), 让 caller 的嵌入点保持干净.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)


def _client_or_none():
    from . import get_client
    return get_client()


# ============================================================
# 表 003: see_entry_detail 直接 inline 调这个
# ============================================================
def record_evidence(session_id: str, uuid: str, detail_dict: dict) -> None:
    """被 infra/core/failure_analyzer/failure_detail.py 调用."""
    if not session_id or not uuid:
        return
    c = _client_or_none()
    if c is None:
        return
    try:
        c.record_evidence(session_id, uuid, detail_dict)
    except Exception as e:
        _logger.debug(f"record_evidence hook skipped: {e}")


# ============================================================
# 表 001: SessionIndex._build() 末尾 inline 调
# ============================================================
def record_run_session_from_index(
    run_id: Optional[str],
    session_id: str,
    index_path: Path,
) -> None:
    """
    读 <root>/.index/<sid>.json, 抽出高频字段 + 整体 raw, 入库.
    run_id=None 时不动 (例如某些阶段 1 内部调用没 run_id).

    by_agent_type 按用户决策 2026-07-25 扁平化为 {name: count, ...},
    详情仍可从 index_raw 取.
    """
    if not run_id or not session_id:
        return
    c = _client_or_none()
    if c is None:
        return
    if not index_path.is_file():
        _logger.debug(f"record_run_session_from_index: index not found: {index_path}")
        return
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        _logger.debug(f"record_run_session_from_index: parse failed: {e}")
        return

    # 扁平化 by_agent_type: {name: count}
    by_agent_type_flat: dict[str, int] = {}
    raw_by = data.get("by_agent_type")
    if isinstance(raw_by, dict):
        for name, info in raw_by.items():
            if isinstance(info, dict):
                cnt = info.get("count", 0)
                try:
                    cnt = int(cnt)
                except Exception:
                    cnt = 0
                by_agent_type_flat[name] = cnt

    try:
        c.record_run_session(
            run_id=run_id,
            session_id=session_id,
            agent_cwd=data.get("agent_cwd"),
            by_agent_type=by_agent_type_flat,
            summary=data.get("summary"),
            index_raw=data,
        )
    except Exception as e:
        _logger.debug(f"record_run_session_from_index: enqueue failed: {e}")


# ============================================================
# 表 002: see-analyze.py 主流程末尾 (post-phase scan)
# ============================================================
def scan_and_record_analysis_reports(run_id: str, reports_dir: Path) -> int:
    """
    扫 evidence/<run_id>/analysis_reports/*.analysis_report.json,
    对每份按 target_file 分桶后写入 see_analysis_report.

    桶规则 (用户决策 2026-07-25):
      - 一个 session 的报告里, target_file 不相同的 sg 会拆成多行
      - target_file 相同的 sg 合并到同一行
      - target_file 为空字符串的 sg 也保留成单独一行,
        subject_target = "<subject_name>@" (空 target 部分)
        DDL 002 uk 仍能匹配 (空字符串占位)
    """
    if not run_id:
        return 0
    if not reports_dir.is_dir():
        _logger.debug(f"scan_analysis_reports: dir not found: {reports_dir}")
        return 0
    c = _client_or_none()
    if c is None:
        return 0

    from .schema import normalize_subject_target, SUBJECT_TARGET_SEP

    count = 0
    for fp in sorted(reports_dir.glob("*.analysis_report.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            _logger.debug(f"scan_analysis_reports: skip {fp.name}: {e}")
            continue
        session_id = data.get("session_id") or fp.name.replace(
            ".analysis_report.json", ""
        )
        subject_name = data.get("subject_name")
        suggestions = data.get("suggestions") or []
        if not subject_name or not isinstance(suggestions, list):
            continue

        # 按 target_file 分桶, 保留首次出现顺序
        buckets: "dict[str, list[dict]]" = {}
        for sg in suggestions:
            tg = sg.get("target_file") or ""    # 关键: 空字符串也算一桶
            buckets.setdefault(tg, []).append(sg)

        for tg, sgs in buckets.items():
            # 保留空 target_file 用 <name>@ 形态 (空 target 部分)
            if tg:
                subject_target = normalize_subject_target(subject_name, tg)
            else:
                subject_target = f"{subject_name}{SUBJECT_TARGET_SEP}"
            try:
                c.record_analysis_report(
                    run_id=run_id,
                    session_id=session_id,
                    subject_target=subject_target,
                    suggestions_json=sgs,   # 该桶内的 sg 数组 (1+ 条)
                )
                count += 1
            except Exception as e:
                _logger.debug(f"scan_analysis_reports enqueue failed: {e}")
    return count


# ============================================================
# 表 004 seed: evolve-discovery 时机调, 先入库占位行
# ============================================================
def seed_evolution_changes_from_discovery(
    run_id: str,
    targets: list[dict],
    reports_dir: Path,
) -> int:
    """
    evolve-discovery 完成拿到 targets[] 后调用:
    对每个 (subject_name, target_file) 占位写一行, 填 suggestions_json,
    原文件 / 新文件先留空, 等 finalize 时补齐.

    targets[] 元素结构: {"subject_name": str, "target_file": str}
    """
    if not run_id or not targets:
        return 0
    c = _client_or_none()
    if c is None:
        return 0

    from .schema import normalize_subject_target

    count = 0
    for t in targets:
        sub = (t.get("subject_name") or "").strip()
        tf = (t.get("target_file") or "").strip()
        if not sub or not tf:
            continue
        try:
            subject_target = normalize_subject_target(sub, tf)
        except ValueError as e:
            _logger.debug(f"seed_evolution_changes skip {sub!r}@{tf!r}: {e}")
            continue

        # 从 reports_dir 反查该 (subject, target) 对应的 suggestions (照 002 桶法重算)
        # 任何 reports 出错都兜底给空 list
        suggestions_for_target: list = []
        try:
            from pathlib import Path
            rdir = Path(reports_dir)
            if rdir.is_dir():
                for fp in rdir.glob("*.analysis_report.json"):
                    try:
                        data = json.loads(fp.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if (data.get("subject_name") or "").strip() != sub:
                        continue
                    sgs = data.get("suggestions") or []
                    for sg in sgs:
                        if (sg.get("target_file") or "") == tf:
                            suggestions_for_target.append(sg)
        except Exception as e:
            _logger.debug(f"seed_evolution_changes read reports failed: {e}")

        try:
            c.record_evolution_change_seeded(
                run_id=run_id,
                subject_target=subject_target,
                suggestions_json=suggestions_for_target,
            )
            count += 1
        except Exception as e:
            _logger.debug(f"seed_evolution_changes enqueue failed: {e}")
    return count


# ============================================================
# 表 004 dispatch-time: prompt_builder.build_agent_call 调用
# ============================================================
def record_evolution_change_dispatch(
    evidence_root: Path,
    run_id: Optional[str],
    subject_name: str,
    target_file: str,
    suggestions: list,
    project_root: Path,
) -> None:
    """
    dispatch 当时保存 (suggestions + 原文件) 到 stash, finalize 时读回 join .change 文件.
    run_id=None 表示 CLI 调试 / 测试场景, 不写 stash.
    """
    if not run_id:
        return
    from . import _stash
    from .schema import normalize_subject_target

    subject_target = normalize_subject_target(subject_name, target_file)
    # 读原文件 (失败填空字符串)
    original_content = ""
    if project_root:
        candidate = project_root / target_file
        if candidate.is_file():
            try:
                original_content = candidate.read_text(encoding="utf-8")
            except Exception:
                pass
    _stash.record(
        evidence_root=evidence_root,
        run_id=run_id,
        subject_target=subject_target,
        suggestions=suggestions,
        original_content=original_content,
    )


# ============================================================
# 表 004 post-scan: see-evolve-finalize.py 调用
# ============================================================
def scan_and_record_evolution_changes(
    run_id: str,
    evidence_root: Path,
    evolution_changes_dir: Path,
    projects_home: Path,
) -> int:
    """
    扫 evolution_changes/*.change, 与 stash join, 读原文件, 入库 see_evolution_change.
    """
    if not run_id or not evolution_changes_dir.is_dir():
        return 0
    c = _client_or_none()
    if c is None:
        return 0

    from . import _stash
    from .schema import normalize_subject_target

    stash = _stash.load_and_clear(evidence_root, run_id)

    count = 0
    for fp in sorted(evolution_changes_dir.glob("*.change")):
        # 解析文件名: <subject_name>__<target_file_with___replaced>.change
        filename = fp.name
        if not filename.endswith(".change"):
            continue
        body = filename[: -len(".change")]
        parts = body.split("__")
        if len(parts) < 2:
            continue
        subject_name = parts[0]
        target_file = "/".join(parts[1:])
        subject_target = normalize_subject_target(subject_name, target_file)
        try:
            new_content = fp.read_text(encoding="utf-8")
        except Exception:
            new_content = ""

        # 与 stash join
        stash_entry = stash.get(subject_target, {})
        suggestions = stash_entry.get("suggestions_json")
        original_content = stash_entry.get("original_content", "")

        # 若 stash 没拿到, 退而求其次从盘读原文件
        if not original_content:
            candidate = projects_home / subject_name / target_file
            if candidate.is_file():
                try:
                    original_content = candidate.read_text(encoding="utf-8")
                except Exception:
                    pass

        try:
            c.record_evolution_change(
                run_id=run_id,
                subject_target=subject_target,
                original_content=original_content or "",
                new_content=new_content or "",
                suggestions_json=suggestions or [],
            )
            count += 1
        except Exception as e:
            _logger.debug(f"scan_evolution_changes enqueue failed: {e}")

    return count


# ============================================================
# 收尾
# ============================================================
def flush(timeout: float = 10.0) -> None:
    from . import flush as _flush
    _flush(timeout=timeout)


def shutdown(timeout: float = 10.0) -> None:
    from . import shutdown as _shutdown
    _shutdown(timeout=timeout)
