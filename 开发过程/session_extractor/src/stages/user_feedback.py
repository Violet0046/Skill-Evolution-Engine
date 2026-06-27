"""user_feedback stage — 把 entry_class=user_input 转成 {uuid, text, timestamp} 列表。

text 为空则跳过该 entry。

"""

from __future__ import annotations

from typing import Any, Dict, List


def extract_user_feedback(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """扫描 user_input 条目拼文本；返回 [{uuid, text, timestamp}, ...]。"""
    out: List[Dict[str, Any]] = []
    for e in entries:
        if e.get("entry_class") != "user_input":
            continue
        content = (e.get("message", {}) or {}).get("content")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    t = item.get("text", "")
                    if isinstance(t, str):
                        parts.append(t)
            text = "\n".join(parts)
        if text:
            out.append({
                "uuid": e.get("uuid", ""),
                "text": text,
                "timestamp": e.get("timestamp", ""),
            })
    return out