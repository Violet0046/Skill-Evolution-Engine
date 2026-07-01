"""session_io — session 文件 IO：加载 + header 提取 + cwd 跳变标记。

3 个公开函数：
- load_session_entries: NDJSON / JSON-array 双格式自适应
- extract_session_header: 从 entries 提取 6 字段 header
- insert_cwd_changes: 检测 cwd 跳变并给原 entry 标 prev_cwd

"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# session header 字段
SESSION_HEADER_FIELDS = [
    "sessionId", "version", "entrypoint", "isSidechain", "userType", "cwd", "slug",
]


def load_session_entries(file_path: str) -> Tuple[List[Dict[str, Any]], str]:
    """从文件加载 entries；支持 NDJSON 与 JSON 数组两种格式。

    返回 (entries, format_hint)；format_hint 为 "ndjson" 或 "json-array"。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    text_stripped = text.lstrip()
    if text_stripped.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 数组解析失败: {e}")
            return [], "json-array"
        if isinstance(data, list):
            entries = [e for e in data if isinstance(e, dict)]
            logger.info(f"从 {file_path} (JSON 数组) 加载了 {len(entries)} 条 entry")
            return entries, "json-array"
        if isinstance(data, dict):
            return [data], "json-array"
        return [], "json-array"

    entries: List[Dict[str, Any]] = []
    for line_num, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict):
                entries.append(entry)
        except json.JSONDecodeError as e:
            logger.warning(f"第{line_num}行 JSON 解析失败: {e}")
    logger.info(f"从 {file_path} (NDJSON) 加载了 {len(entries)} 条 entry")
    return entries, "ndjson"


def extract_session_header(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从 entries 中提取 session header（取第一个有这些字段的 entry）。

    缺位填 None。
    """
    header: Dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for f in SESSION_HEADER_FIELDS:
            if f in entry and f not in header:
                header[f] = entry[f]
        if len(header) == len(SESSION_HEADER_FIELDS):
            break
    for f in SESSION_HEADER_FIELDS:
        if f not in header:
            header[f] = None
    return header


def insert_cwd_changes(entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """检测 cwd 跳变，给跳变后 entry 标 prev_cwd 字段。

    相邻 entry 的 cwd 字段值不同即视为跳变；跳变时给当前 entry 写 prev_cwd。
    """
    if not entries:
        return entries, 0

    prev_cwd = None
    cwd_changes = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cur_cwd = entry.get("cwd")
        if cur_cwd is not None and prev_cwd is not None and cur_cwd != prev_cwd:
            entry["prev_cwd"] = prev_cwd       # mutate 标记跳变点
            cwd_changes += 1
        if cur_cwd is not None:
            prev_cwd = cur_cwd
    return entries, cwd_changes