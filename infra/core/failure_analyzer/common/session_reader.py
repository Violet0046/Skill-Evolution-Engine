"""
session_reader.py —— 双格式 entry 迭代器。

数据约定（与 simplify_sessions.py 输出对齐）：
- 主文件：  <root>/<session_id>.jsonl  实际为 **JSON 数组**（顶层 `[...]`）
            800 条左右；第一条是 `{"session": {...}}` 头；其余是 entry
- 子文件：  <root>/<session_id>/subagents/agent-<id>.jsonl  为 **NDJSON**
            第一条仍是 `{"session": {...}}` 头（isSidechain=true），其余是 entry

为什么需要双格式适配：
- simplify_sessions.py 把主文件序列化为"人类可读"的 JSON 数组（用户偏好）
- 子文件为节省 IO 用了 NDJSON（一行一条）
- 工具集需要透明地同时处理两种格式，让上层调用不感知差异

公开 API：
- iter_session_file(path)              -> Iterator[(entry_or_header, is_header)]
- load_main_session(root, sid)         -> (header, entries_list)
- load_subagent_files(root, sid)       -> {agent_id: (header, entries_list)}
- find_entry_by_uuid(root, sid, uuid)  -> Optional[Dict]  （含 source 标识）
- collect_all_entries(root, sid)       -> List[Dict]  （主+子全量，含 source 字段）

性能说明：
- 全部走纯文件 IO，不引入 pandas / pyarrow 等重依赖
- 7h / 2,398 entry session 加载 < 100ms（实测 SSD）
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部：单文件加载（自适应格式）
# ---------------------------------------------------------------------------

def _iter_session_file(path: str) -> Iterator[Tuple[Dict[str, Any], bool]]:
    """迭代单文件的所有"对象"。

    产出：((entry_or_header_dict, is_header))
        - 第一条 `{"session": ...}` 标 is_header=True
        - 其余 entry 标 is_header=False

    自适应 NDJSON / JSON-array（顶部 `[` 判定）。
    """
    p = Path(path)
    if not p.exists():
        return

    text = p.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if not stripped:
        return

    if stripped.startswith("["):
        # JSON 数组
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 数组解析失败: {path}, {e}")
            return
        if isinstance(data, list):
            for obj in data:
                if not isinstance(obj, dict):
                    continue
                is_header = "session" in obj and set(obj.keys()) <= {"session"}
                yield obj, is_header
        elif isinstance(data, dict):
            is_header = "session" in data
            yield data, is_header
    else:
        # NDJSON（一行一条）
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"NDJSON 解析失败: {path}, {e}")
                continue
            if not isinstance(obj, dict):
                continue
            is_header = "session" in obj and set(obj.keys()) <= {"session"}
            yield obj, is_header


# ---------------------------------------------------------------------------
# 公开：主 session + subagent 文件加载
# ---------------------------------------------------------------------------

def load_main_session(root: str, session_id: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """加载主 session 文件。

    返回：
        (header_dict, entries_list)
        - 文件不存在时返回 (None, [])
        - header 为 None 表示文件无 session 头
    """
    main_path = Path(root) / f"{session_id}.jsonl"
    if not main_path.exists():
        return None, []

    header: Optional[Dict[str, Any]] = None
    entries: List[Dict[str, Any]] = []
    for obj, is_header in _iter_session_file(str(main_path)):
        if is_header:
            header = obj.get("session")
        else:
            entries.append(obj)
    return header, entries


def load_subagent_files(
    root: str, session_id: str,
) -> Dict[str, Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]]:
    """加载所有 subagent 文件。

    返回：
        {agent_id: (header, entries_list)}
        agent_id 取自文件名 `agent-<id>.jsonl` → `<id>`

    注意：
    - subagent 文件不存在时返空 dict
    - 单个 subagent 文件解析失败仅记 logger，不影响其他文件
    """
    sub_dir = Path(root) / session_id / "subagents"
    if not sub_dir.is_dir():
        return {}

    result: Dict[str, Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]] = {}
    for sub_file in sorted(sub_dir.glob("agent-*.jsonl")):
        # agent-a1b2c3d4e5f6g7h8.jsonl → a1b2c3d4e5f6g7h8
        agent_id = sub_file.stem.replace("agent-", "", 1)
        header: Optional[Dict[str, Any]] = None
        entries: List[Dict[str, Any]] = []
        try:
            for obj, is_header in _iter_session_file(str(sub_file)):
                if is_header:
                    header = obj.get("session")
                else:
                    entries.append(obj)
        except Exception as e:
            logger.warning(f"subagent 文件解析失败: {sub_file}, {e}")
            continue
        result[agent_id] = (header, entries)
    return result


def collect_all_entries(
    root: str, session_id: str,
) -> List[Dict[str, Any]]:
    """收集主+子全量 entries，给每条注入 `source` 字段。

    source 取值：
        - "main"                 主流程
        - "subagent:<agent_id>"  subagent 实例
        - 此外附 `parent_source="subagent:<agent_id>"`（仅 subagent 条目）

    返回：
        List[entry_dict]，每条 dict 含原字段 + 注入的 _source 字段
    """
    out: List[Dict[str, Any]] = []

    _, main_entries = load_main_session(root, session_id)
    for e in main_entries:
        e["_source"] = "main"
        out.append(e)

    sub_map = load_subagent_files(root, session_id)
    for agent_id, (_h, entries) in sub_map.items():
        for e in entries:
            e["_source"] = f"subagent:{agent_id}"
            out.append(e)

    return out


# ---------------------------------------------------------------------------
# 公开：按 uuid 反查单条 entry
# ---------------------------------------------------------------------------

def find_entry_by_uuid(
    root: str, session_id: str, uuid: str,
    use_raw_root: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """按 uuid 反查单条 entry（全文件扫，找不到 fallback）。

    实现：
        先在 root 找，找不到再 fallback 到 use_raw_root（若提供）

    注意：慢路径，仅在不知道 source 时用。已知 source 请用 find_entry_in_file()。
    """
    roots: List[Tuple[str, str]] = [(root, "")]
    if use_raw_root:
        roots.append((use_raw_root, "raw:"))

    for cur_root, prefix in roots:
        # 主文件
        _, main_entries = load_main_session(cur_root, session_id)
        for e in main_entries:
            if e.get("uuid") == uuid:
                return e, f"{prefix}main"

        # subagent 文件
        sub_map = load_subagent_files(cur_root, session_id)
        for agent_id, (_h, entries) in sub_map.items():
            for e in entries:
                if e.get("uuid") == uuid:
                    return e, f"{prefix}subagent:{agent_id}"

    return None, None


def find_entry_in_file(
    root: str, session_id: str, uuid: str, source: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """已知 source 时，按 uuid 在单文件内找 entry（快速路径）。

    参数：
        root:      数据根目录
        session_id: session UUID
        uuid:      目标 entry UUID
        source:    "main" / "subagent:<agent_id>"

    返回：
        (entry_dict, source_str)
        - 找不到时 (None, None)
        - source_str 原样返回

    性能：
        已知 source 时只 load 1 个文件（不扫其他 36 个 subagent），~5ms。
    """
    if source == "main":
        _, entries = load_main_session(root, session_id)
    elif source.startswith("subagent:"):
        agent_id = source.split(":", 1)[1]
        sub_map = load_subagent_files(root, session_id)
        _, entries = sub_map.get(agent_id, (None, []))
    else:
        return None, None

    for e in entries:
        if e.get("uuid") == uuid:
            return e, source
    return None, None


# ---------------------------------------------------------------------------
# 公开：uuid → 上下文（前后 N 条）
# ---------------------------------------------------------------------------

