"""
工具函数

提供JSONL文件的加载和保存功能。
"""

import json
import logging
from typing import List, Dict, Any

# 配置日志
logger = logging.getLogger(__name__)


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """
    加载JSONL文件
    
    每行是一个JSON对象,空行会被跳过。
    如果某行JSON解析失败,会记录警告并跳过该行。
    """
    entries = []
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                logger.warning(f"第{line_num}行JSON解析失败: {e}")
    
    logger.info(f"从 {file_path} 加载了 {len(entries)} 条记录")
    return entries


def save_jsonl(entries: List[Dict[str, Any]], file_path: str) -> None:
    """
    保存JSONL文件
    
    每个条目占一行,使用JSON格式。
    """
    with open(file_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    logger.info(f"已将 {len(entries)} 条记录保存到 {file_path}")
