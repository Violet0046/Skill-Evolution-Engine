"""
Session条目分类器

根据entry的type字段和message.content中的type字段,将条目分为以下类别:
- user类型: user_command、user_input、tool_result
- assistant类型: ai_text、ai_tool_call
- attachment 类型：细化为 attachment.{subtype}（如 attachment.hook_success）
- 其他系统类型：file-history-snapshot、permission-mode、ai-title、queue-operation、last-prompt、system、progress

"""

from typing import Dict, Any


def classify_entry(entry: Dict[str, Any]) -> str:
    """
    根据entry的type和message.content判断entry_class

    分类规则：
    - user类型：
      - user_command：message.content包含<>且尖括号里面有command
      - user_input：message.content中的type为text
      - tool_result：message.content中的type为tool_result
    - assistant类型：
      - ai_text：message.content中的type为text
      - ai_tool_call：message.content中的type为tool_use
    - attachment 类型：细化为 attachment.{subtype}（如 attachment.hook_success）
    - 其他系统类型：file-history-snapshot、permission-mode、ai-title、queue-operation、last-prompt、system、progress
    """
    entry_type = entry.get("type", "")

    # attachment 类型：进一步细化为 attachment.{subtype}
    if entry_type == "attachment":
        att_type = (entry.get("attachment", {}) or {}).get("type")
        if att_type:
            return f"attachment.{att_type}"
        return "attachment"

    # 其他系统类型（system / queue-operation / last-prompt / ...）原样返回
    if entry_type in ["system", "queue-operation", "last-prompt",
                       "file-history-snapshot", "permission-mode", "ai-title","progress"]:
        return entry_type

    # 处理user类型
    if entry_type == "user":
        result = _classify_user_entry(entry)
        if result is not None:
            return result

    # 处理assistant类型
    if entry_type == "assistant":
        return _classify_assistant_entry(entry)

    # 如果没有匹配到任何类型，返回None
    return None

def _classify_user_entry(entry: Dict[str, Any]) -> str:
    """分类user类型的entry"""
    message = entry.get("message", {})
    content = message.get("content", "")

    # 检查是否是user_command（content是字符串且包含<>command）
    if isinstance(content, str):
        if "<" in content and ">" in content and "command" in content.lower():
            return "user_command"
        # 普通用户输入（字符串形式）
        return "user_input"

    # 检查content数组
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "tool_result":
                    return "tool_result"
                elif item_type == "text":
                    return "user_input"

    # 如果没有匹配到任何类型，返回None（不返回默认类型）
    return None


def _classify_assistant_entry(entry: Dict[str, Any]) -> str:
    """分类assistant类型的entry"""
    message = entry.get("message", {})
    content = message.get("content", [])

    if isinstance(content, list) and len(content) > 0:
        item = content[0]
        if isinstance(item, dict):
            item_type = item.get("type", "")
            if item_type == "text":
                return "ai_text"
            elif item_type == "tool_use":
                return "ai_tool_call"

    # 如果没有匹配到任何类型，返回None
    return None