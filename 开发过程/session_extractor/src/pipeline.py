"""
v4 collector 主流程编排（pipeline）。

10 步流水线：
1. 加载 entries（NDJSON / JSON-array）   session_io.py  load_session_entries
2. 提取 session header    session_io.py   extract_session_header
3. classify 每个 entry（标 entry_class；attachment 细化为 attachment.{subtype}）
4. sort by timestamp
5. 标记 cwd 跳变（mutate entry 加 prev_cwd）   session_io.py   insert_cwd_changes
6. simplify（按 config 字段白名单 + truncate 规则）
7. detector 全部跑一遍
8. 计算 execution_pattern
9. 提取 user_feedback
10. 合并为 EvidenceBundle + 写到输出文件

详细数据流图见 ARCHITECTURE.md §2。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from src.detectors import run_all
from src.models import ClassifiedEntry, DetectorContext, EvidenceBundle
from src.simplify import load_config, simplify_entries
from src.spec_loader import load_spec
from src.stages.bundle_writer import make_empty_bundle, write_bundle
from src.stages.execution_pattern import compute_execution_pattern
from src.stages.user_feedback import extract_user_feedback
from src.simplify.classifier import classify_entry
from src.util.session_io import (
    load_session_entries,
    extract_session_header,
    insert_cwd_changes,
)
from src.util.timestamp import sort_by_timestamp


logger = logging.getLogger(__name__)


# detector 启用顺序的默认值（与 5 个 detector 全部跑等价）
DEFAULT_ENABLED_DETECTORS = [
    "state_machine", "gate", "review_contract", "user_confirmation", "symlink",
]


def _classify_entries(entries: List[Dict[str, Any]]) -> None:
    """给每条 entry 标 entry_class（classifier 已输出 attachment.{subtype}，无需补丁）。"""
    for e in entries:
        e["entry_class"] = classify_entry(e)


def _first_timestamp(entries: List[Dict[str, Any]]) -> Optional[str]:
    """返回排序后第一个有 timestamp 的 entry 的 timestamp。"""
    for e in entries:
        ts = e.get("timestamp")
        if ts:
            return ts
    return None


def _last_timestamp(entries: List[Dict[str, Any]]) -> Optional[str]:
    """返回排序后最后一个有 timestamp 的 entry 的 timestamp。"""
    for e in reversed(entries):
        ts = e.get("timestamp")
        if ts:
            return ts
    return None


def _build_ctx_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """把 spec 顶层 4 key 平铺到 ctx.spec，保留 detector 走的嵌套路径。

    spec_loader 返回 {"spec": {...}, "hooks": {...}, "subagents": {...}, "constraints": {...}}。
    detector 按 ctx.spec["phases"] / ctx.spec["subagents"]["review-agent"] /
    ctx.spec["environment"]["auto_confirm_keys"] 等嵌套路径读取。
    """
    ctx_spec: Dict[str, Any] = {}
    for top_key, nested_key in (
        ("spec", None),
        ("subagents", "subagents"),
        ("environment", "environment"),
        ("hooks", "hooks"),
    ):
        v = spec.get(top_key)
        if isinstance(v, dict):
            if nested_key is None:
                ctx_spec.update(v)
            else:
                ctx_spec[nested_key] = v
    return ctx_spec


def run(
    input_path: str,
    output_path: str,
    config_path: Optional[str] = None,
    spec_dir: Optional[str] = None,
    simplify: bool = True,
    truncate: Optional[bool] = None,  # None = 用 config 默认值
    enabled_detectors: Optional[List[str]] = None,
    skip_detectors: bool = False,
    env: Optional[Dict[str, str]] = None,
    quiet: bool = False,
) -> EvidenceBundle:
    """执行 v4 collector 主流程（10 步）；返回 EvidenceBundle。"""
    if env is None:
        env = dict(os.environ)

    # 1) 加载
    entries, _ = load_session_entries(input_path)
    if not entries:
        logger.warning("输入文件无有效 entry，输出空 bundle")
        empty = make_empty_bundle()
        write_bundle(output_path, empty, trace=[])
        return empty

    # 2) header（6 字段从 entry 提取；start_time/end_time 待排序后从时序推导）
    session_header = extract_session_header(entries)

    # 3) classify  4) sort  5) cwd_change
    _classify_entries(entries)
    entries = sort_by_timestamp(entries)
    entries, cwd_changes = insert_cwd_changes(entries)

    # 5.5) 时序字段注入（必须在 sort_by_timestamp 之后，否则 entries[0]/-1 不准）
    session_header["start_time"] = _first_timestamp(entries)
    session_header["end_time"] = _last_timestamp(entries)

    # 6) simplify（5 个 detector 吃 simplify 后的 entries）
    # 之前保留 raw_entries 让 detector 吃原始 entry——但 simplify 删除的字段都是对进化无用的元信息
    # (sessionId/version/entrypoint/isSidechain/userType/cwd)，不影响 detector 判断。
    # 统一用 simplify 后 entries 让 pipeline 流程更顺畅（少一份副本）。
    if simplify and config_path and os.path.isfile(config_path):
        config = load_config(config_path)
        if truncate is not None:
            config["truncate_enabled"] = truncate
        entries = simplify_entries(entries, config_path)
    else:
        config = {"truncate_enabled": truncate if truncate is not None else False}

    # 6.5) cwd 跳变信息已通过 insert_cwd_changes（step 5）写入 entry.prev_cwd
    # simplify 后 entry 不再含 cwd（黑名单 drop），但 prev_cwd 保留供 detector 使用。
    # symlink detector 看到 prev_cwd 也能识别"cwd 跳到物理源"的跳变点。

    # 7) detectors
    classified = [ClassifiedEntry(raw=e, entry_class=e.get("entry_class", ""))
                  for e in entries]
    spec = load_spec(spec_dir)
    ctx = DetectorContext(spec=_build_ctx_spec(spec), env=env, cwd_realpath_cache={})

    if skip_detectors:
        state_machine: Dict[str, Any] = {"phases": [], "transitions": [], "unexpected_exits": []}
        constraint_events: List[Dict[str, Any]] = []
        symlink_hop: List[Dict[str, Any]] = []
        warnings: List[str] = ["detectors skipped"]
    else:
        results = run_all(classified, ctx, enabled=enabled_detectors)
        sm = results.get("state_machine", [])
        state_machine = sm[0] if sm else {"phases": [], "transitions": [], "unexpected_exits": []}
        constraint_events = []
        for name in ("gate", "review_contract"):
            constraint_events.extend(results.get(name, []))
        symlink_hop = results.get("symlink", [])
        warnings = []

    # 8) execution_pattern  9) user_feedback
    execution_pattern = compute_execution_pattern(entries, state_machine)
    user_feedback = extract_user_feedback(entries)

    # 10) bundle + write
    bundle = EvidenceBundle(
        schema_version="4.0",
        session=session_header,
        cwd_changes=cwd_changes,
        trace=entries,
        state_machine=state_machine,
        constraint_events=constraint_events,
        user_feedback=user_feedback,
        symlink_hop=symlink_hop,
        execution_pattern=execution_pattern,
        detector_meta={
            "enabled": enabled_detectors if enabled_detectors else DEFAULT_ENABLED_DETECTORS,
            "spec_loaded": bool(spec),
            "truncate_enabled": config.get("truncate_enabled", False),
            "warnings": warnings,
        },
    )
    if not quiet:
        logger.info(
            f"v4 collector: trace={len(entries)} entries, "
            f"phases={len(state_machine['phases'])}, "
            f"constraint_events={len(constraint_events)}, "
            f"user_feedback={len(user_feedback)}"
        )
    write_bundle(output_path, bundle, trace=entries)
    return bundle