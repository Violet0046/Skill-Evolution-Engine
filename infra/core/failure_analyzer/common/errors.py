"""
errors.py —— 工具集统一异常与 JSON 友好输出。

设计目标：
- **永不抛异常给调用方**（除编程错误如 TypeError）。找不到 session / uuid /
  模式不存在时一律返回 dict，让 LLM 用 {"error": "..."} 字段做兜底。
- 退出码恒为 0（让 CLI 脚本的 LLM 调用方不要把"找不到"当 fatal）。

返回约定：
- 成功：返回业务 dict，**不带** error 字段
- 失败：返回 `{"error": "<message>", "session_id": "...", ...}`，可选加 context

error 字段值是**人类可读**的中文短句（LLM 直接消费）。
堆栈信息走 logger，stdout 留干净。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def err(message: str, **context: Any) -> Dict[str, Any]:
    """构造统一错误返回 dict。

    参数：
        message: 中文短句，描述失败原因
        **context: 附加字段（如 session_id / uuid / pattern 等便于排错）

    返回：
        {"error": message, **context}  （至少含 error 字段）
    """
    if context:
        logger.debug(f"工具错误: {message} | context={context}")
    else:
        logger.debug(f"工具错误: {message}")
    return {"error": message, **context}