#!/usr/bin/env python3
"""
分类器覆盖率测试脚本

遍历指定目录下的所有JSONL文件，测试分类器是否能覆盖所有entry类型。
未覆盖的entry会输出到errentry.jsonl文件。
"""

import sys
import os
import json
import logging
from pathlib import Path
from collections import Counter

# 添加src目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

from src.util.classifier import classify_entry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def find_jsonl_files(directory: str) -> list:
    """查找目录下的所有JSONL文件"""
    jsonl_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".jsonl"):
                jsonl_files.append(os.path.join(root, file))
    return jsonl_files


def _iter_entries(file_path: str):
    """逐 entry 产出 (entry, line_number)。

    支持两种文件格式：
    - NDJSON：每行一个 JSON 对象
    - JSON 数组：单文件 `[obj, obj, ...]`（多行或单行）
    注释型/损坏行记 warning 跳过。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        first = None
        for line in f:
            stripped = line.strip()
            if stripped:
                first = stripped
                break
        if first is None:
            return
        f.seek(0)
        if first.startswith("["):
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"JSON数组解析失败: {file_path}, {e}")
                return
            if isinstance(data, list):
                for idx, entry in enumerate(data, 1):
                    yield entry, idx
            else:
                yield data, 1
            return
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line), line_num
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {file_path}:{line_num}, {e}")


def test_classifier_on_file(file_path: str, error_entries: list) -> dict:
    """
    测试单个文件中所有entry的分类

    返回：分类统计 Counter
    """
    classes = []

    for entry, line_num in _iter_entries(file_path):
        if not isinstance(entry, dict):
            logger.warning(f"非 dict entry: {file_path}:{line_num}, type={type(entry).__name__}, value={str(entry)[:60]!r}")
            continue

        entry_class = classify_entry(entry)

        if entry_class is None:
            entry["_source_file"] = file_path
            entry["_line_number"] = line_num
            error_entries.append(entry)
            logger.warning(f"未覆盖的entry: {file_path}:{line_num}, type={entry.get('type')}")

        classes.append(entry_class)

    return Counter(classes)


def main():
    if len(sys.argv) != 2:
        print("用法: python test_coverage.py <sessions_directory>")
        sys.exit(1)
    
    sessions_dir = sys.argv[1]
    
    if not os.path.isdir(sessions_dir):
        logger.error(f"目录不存在: {sessions_dir}")
        sys.exit(1)
    
    # 查找所有JSONL文件
    jsonl_files = find_jsonl_files(sessions_dir)
    logger.info(f"找到 {len(jsonl_files)} 个JSONL文件")
    
    # 统计
    total_entries = 0
    total_classes = Counter()
    error_entries = []
    file_count = 0
    
    # 处理每个文件
    for file_path in jsonl_files:
        logger.info(f"处理: {file_path}")
        file_count += 1
        
        classes = test_classifier_on_file(file_path, error_entries)
        total_classes += classes
        total_entries += sum(classes.values())
    
    # 输出统计结果
    logger.info("=" * 60)
    logger.info(f"处理完成:")
    logger.info(f"  文件数量: {file_count}")
    logger.info(f"  总entry数: {total_entries}")
    logger.info(f"  未覆盖entry数: {len(error_entries)}")
    logger.info("")
    logger.info("分类统计:")
    for cls, count in total_classes.most_common():
        if cls is None:
            logger.info(f"  未覆盖: {count}")
        else:
            logger.info(f"  {cls}: {count}")
    
    # 保存未覆盖的entry
    if error_entries:
        error_file = os.path.join(os.path.dirname(__file__), "errentry.jsonl")
        with open(error_file, "w", encoding="utf-8") as f:
            for entry in error_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"\n未覆盖的entry已保存到: {error_file}")
        
        # 显示未覆盖entry的type分布
        error_types = Counter(entry.get("type") for entry in error_entries)
        logger.info("未覆盖entry的type分布:")
        for type_name, count in error_types.most_common():
            logger.info(f"  {type_name}: {count}")
    else:
        logger.info("\n所有entry都已被分类器覆盖!")


if __name__ == "__main__":
    main()
