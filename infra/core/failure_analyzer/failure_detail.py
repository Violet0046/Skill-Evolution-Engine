"""
failure_detail.py —— see_entry_detail 工具

用途：
  按 (session_id, uuid) 取出单条 entry 的完整上下文，是 see_* 工具
  集中"最深度"的查询。

  LLM 通常在 see_find 拿到 hit uuid 后调用本工具，看
  - 完整 input_params（不被 simplify 截断）
  - 完整 error_output
  - 同源 reasoning（最近的 ai_text，作为 LLM 当时的"思考"）
  - files_read / files_written

参数：
  session_id:        session UUID
  uuid:              entry UUID
  root:              简化版数据根目录
  raw_root:          原始版数据根目录（用于 use_raw=True 时回退）
  use_raw:           True → 从 raw_root 读（取完整 toolUseResult）
  include_reasoning: True → 同时返回最近的 ai_text（默认 True）
  include_file_context: True → 抽取本 entry 涉及的文件（默认 True）

输出示例：
{
  "uuid": "dbad6dda-...",
  "entry_class": "tool_result",
  "is_error": true,
  "tool_name": "Bash",
  "tool_use_id": "call_20d4238199c34a67a79de6fd",
  "timestamp": "2026-06-17T01:54:05.272Z",
  "source": "main",
  "input_params": {"command": "python3 .claude/skills/查询需求信息/scripts/query_simple.py ..."},
  "error_output": "Error: Exit code 1\nTraceback ...\nImportError: No module named requests",
  "output_summary": null,
  "reasoning": "<think>我需要先调用查询需求信息 skill 来获取 RAN-7961869 的需求详情...</think>",
  "files_read": [".claude/skills/查询需求信息/scripts/query_simple.py"],
  "files_written": []
}

返回：
  - 正常：业务 dict
  - 找不到 session：{"error": "session not found: ..."}
  - 找不到 uuid：{"error": "uuid not found: ..."}
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .common.errors import err
from .common.index_store import SessionIndex, _get_tool_name_from_call
from .common.session_reader import find_entry_by_uuid, find_entry_in_file

logger = logging.getLogger(__name__)


def _extract_input_params(call_entry: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """从 ai_tool_call entry 提取 input dict。"""
    if not call_entry:
        return None
    content = call_entry.get("message", {}).get("content", [])
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict):
            inp = item.get("input")
            if isinstance(inp, dict):
                return inp
    return None


def _extract_error_output(result_entry: Dict[str, Any]) -> Optional[str]:
    """取 tool_result 的完整错误输出（不截断到 80）。"""
    content = result_entry.get("message", {}).get("content", [])
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict):
            err_text = item.get("content", "") or ""
            if err_text:
                return err_text
    tur = result_entry.get("toolUseResult")
    if isinstance(tur, str):
        return tur
    return None


def _is_error_entry(entry: Dict[str, Any]) -> bool:
    """entry 是否带 is_error=true。"""
    content = entry.get("message", {}).get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("is_error"):
                return True
    return False


def _extract_text_from_ai_text(entry: Dict[str, Any], max_len: int = 2000) -> Optional[str]:
    """从 ai_text entry 抽取 text 字段（截到 max_len）。"""
    content = entry.get("message", {}).get("content", [])
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict):
            text = item.get("text", "") or ""
            if text:
                return text[:max_len]
    return None


def see_entry_detail(
    session_id: str,
    uuid: str,
    root: str | None = None,
    raw_root: str | None = None,
    use_raw: bool = False,
    include_reasoning_before: bool = True,
    include_reasoning_after: bool = True,
) -> Dict[str, Any]:
    """see_entry_detail 主入口。"""
    if root is None:
        # 默认：项目根/evidence/projects-simplified
        root = str(Path(__file__).resolve().parents[3] / "evidence" / "projects-simplified")
    if raw_root is None:
        # 默认从 simplified 同级目录的 projects/
        raw_root = str(Path(root).parent / "projects")

    # 1) session 存在性
    main_path = Path(root) / f"{session_id}.jsonl"
    if not main_path.exists():
        return err(f"session not found: {session_id}", session_id=session_id, root=root)

    # 2) 找 entry —— 优先走索引快路径
    entry, source, file_entries, agent_type, index_rec = None, None, None, None, None

    # 2a) 错误 uuid：查索引拿到 source + agent_type，直接 load 单文件（~5ms）
    if not use_raw:
        try:
            idx = SessionIndex(session_id, root)
            index_rec = idx.find_uuid_record(uuid)
            if index_rec:
                src = index_rec.get("source", "main")
                agent_id_from_rec = index_rec.get("agent_id")
                agent_type = index_rec.get("agent_type", "main" if src == "main" else "unknown")
                entry, source = find_entry_in_file(root, session_id, uuid, src)
                if entry:
                    # 缓存 file_entries 供下游复用（避免再 load 一次）
                    if src == "main":
                        from .common.session_reader import load_main_session
                        _, file_entries = load_main_session(root, session_id)
                    else:
                        agent_id = agent_id_from_rec or src.split(":", 1)[1]
                        from .common.session_reader import load_subagent_files
                        sub_map = load_subagent_files(root, session_id)
                        _, file_entries = sub_map.get(agent_id, (None, []))
        except Exception as e:
            logger.debug(f"索引快路径失败，fallback 全扫: {e}")

    # 2b) fallback：全扫（或 use_raw=True 时必须走 raw_root）
    if not entry:
        entry, source = find_entry_by_uuid(
            root, session_id, uuid,
            use_raw_root=raw_root if use_raw else None,
        )
        # 顺手 load 对应文件供下游复用
        if entry:
            if source == "main" or source == "raw:main":
                from .common.session_reader import load_main_session
                cur_root = raw_root if (use_raw and source.startswith("raw:")) else root
                _, file_entries = load_main_session(cur_root, session_id)
            elif source.startswith("subagent:") or source.startswith("raw:subagent:"):
                agent_id = source.split(":", 1)[1]
                from .common.session_reader import load_subagent_files
                cur_root = raw_root if (use_raw and source.startswith("raw:")) else root
                sub_map = load_subagent_files(cur_root, session_id)
                _, file_entries = sub_map.get(agent_id, (None, []))
    if not entry:
        return err(
            f"uuid not found: {uuid}",
            session_id=session_id, uuid=uuid,
        )

    # 3) 提取核心字段（v1.7：只保留 5 个聚焦字段）
    is_error = _is_error_entry(entry)

    # 找对应 ai_tool_call（用于取 input_params + tool_name）
    call_uuid = entry.get("sourceToolAssistantUUID")
    call_entry: Optional[Dict[str, Any]] = None
    if call_uuid and file_entries:
        for e in file_entries:
            if e.get("entry_class") == "ai_tool_call" and e.get("uuid") == call_uuid:
                call_entry = e
                break

    tool_name = _get_tool_name_from_call(call_entry)
    input_params = _extract_input_params(call_entry)
    error_output = _extract_error_output(entry) if is_error else None

    # 4) reasoning_before（target 之前最近的 ai_text，模型事前计划）
    # 5) reasoning_after（target 之后最近的 ai_text，模型事后归因）
    reasoning_before: Optional[str] = None
    reasoning_after: Optional[str] = None
    if (include_reasoning_before or include_reasoning_after) and file_entries:
        # 找 target 在 file_entries 中的索引
        target_idx = None
        for i, e in enumerate(file_entries):
            if e.get("uuid") == uuid:
                target_idx = i
                break
        if target_idx is not None:
            if include_reasoning_before:
                # 向前找最近的 ai_text
                for i in range(target_idx - 1, -1, -1):
                    e = file_entries[i]
                    if e.get("entry_class") == "ai_text":
                        reasoning_before = _extract_text_from_ai_text(e)
                        break
            if include_reasoning_after:
                # 向后找最近的 ai_text（更倾向 AFTER，失败分析更关注事后归因）
                for i in range(target_idx + 1, len(file_entries)):
                    e = file_entries[i]
                    if e.get("entry_class") == "ai_text":
                        reasoning_after = _extract_text_from_ai_text(e)
                        break

    # 6) 5 字段聚焦输出（按时间序 T1→T2→T3→T4）
    return {
        "reasoning_before": reasoning_before,  # T1: 事前计划
        "tool_name": tool_name,                # T2a
        "input_params": input_params,          # T2b
        "error_output": error_output,          # T3: 失败信息（成功时 null）
        "reasoning_after": reasoning_after,    # T4: 事后归因
    }
