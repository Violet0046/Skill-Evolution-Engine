"""
时间戳解析与排序工具

提供时间戳解析和按时间戳排序的功能。
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

# 配置日志
logger = logging.getLogger(__name__)


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    解析时间戳字符串
    
    支持以下格式: 
    - ISO格式带毫秒和Z: 2026-05-09T03:07:09.950Z
    - ISO格式带毫秒: 2026-05-09T03:07:09.950
    - ISO格式不带毫秒: 2026-05-09T03:07:09
    
    如果解析失败,返回datetime.min
    """
    # 如果没有时间戳，返回一个很早的时间
    if not timestamp_str:
        return datetime.min
    
    # 处理ISO格式时间戳
    try:
        # 移除末尾的Z（如果有）
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1]
        # 使用strptime解析
        return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        try:
            # 尝试不带毫秒的格式
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            # 如果解析失败，返回一个很早的时间
            logger.warning(f"无法解析时间戳: {timestamp_str}")
            return datetime.min


def sort_by_timestamp(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按时间戳排序
    
    没有时间戳的条目会排在最前面。
    """
    sorted_entries = sorted(entries, key=lambda x: parse_timestamp(x.get("timestamp", "")))
    logger.info(f"已按时间戳排序 {len(sorted_entries)} 条记录")
    return sorted_entries
