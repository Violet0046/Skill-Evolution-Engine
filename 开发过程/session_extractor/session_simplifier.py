#!/usr/bin/env python3
"""
Session处理脚本（v3）

输入：原始 session JSONL / JSON-array 文件
输出：
  - 第 1 行：{"session": {...}, "cwdChanges": N}
  - 2+ 行：NDJSON entries（含 classifier / simplifier 处理 + 自动 cwd_change 插入）

CLI：
  python3 session_simplifier.py <input_file> <output_file> [--no-simplify] [--truncate]
"""

import sys
import os
import json
import uuid
import logging
import argparse

# 添加src目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

from src.classifier import classify_entry
from src.timestamp import sort_by_timestamp
from src.simplifier import simplify_entries, load_config
from src.utils import save_jsonl

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "entry_fields_config.json")

# session header 字段（v3）
SESSION_HEADER_FIELDS = ["sessionId", "version", "entrypoint", "isSidechain", "userType", "cwd"]


def load_session_entries(file_path: str):
    """加载 session 条目。兼容 NDJSON 与 JSON 数组两种格式。

    返回 (entries, format_hint) 其中 format_hint 为 "ndjson" 或 "json-array"。
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
            logger.info(f"从 {file_path} (单 JSON 对象) 加载了 1 条 entry")
            return [data], "json-array"
        return [], "json-array"

    entries = []
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


def extract_session_header(entries):
    """从 entries 中提取 session header 6 字段。

    策略：扫所有 entry 取第一个有这些字段的 entry；缺失字段填空值。
    """
    header: Dict[str, object] = {}
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


def insert_cwd_changes(entries):
    """主流程扫描：发现 cwd 跳变时在跳变后插入 cwd_change entry。

    规则：相邻 entry 的 cwd 字段值不同即视为跳变；插入位置在跳变后那条 entry 之后。
    """
    if not entries:
        return entries, 0

    result: list = []
    prev_cwd = None
    cwd_changes = 0

    for entry in entries:
        if not isinstance(entry, dict):
            result.append(entry)
            continue

        cur_cwd = entry.get("cwd")
        result.append(entry)

        if cur_cwd is not None and prev_cwd is not None and cur_cwd != prev_cwd:
            change_entry = {
                "type": "cwd_change",
                "entry_class": "cwd_change",
                "uuid": str(uuid.uuid4()),
                "timestamp": entry.get("timestamp"),
                "prevCwd": prev_cwd,
                "cwd": cur_cwd,
            }
            result.append(change_entry)
            cwd_changes += 1

        if cur_cwd is not None:
            prev_cwd = cur_cwd

    return result, cwd_changes


def process_session(input_file: str, output_file: str, simplify: bool = True, truncate: bool = False) -> None:
    """
    处理 session 文件。

    参数：
        input_file: 输入文件路径
        output_file: 输出文件路径
        simplify: 是否精简字段（默认 True）
        truncate: 是否启用 truncation 规则（默认 False）
    """
    if os.path.isdir(output_file):
        raise ValueError(f"输出路径是目录而非文件: {output_file}")

    entries, fmt = load_session_entries(input_file)
    if not entries:
        logger.warning("输入文件无有效 entry，输出空")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({"session": {f: None for f in SESSION_HEADER_FIELDS}, "cwdChanges": 0}, ensure_ascii=False) + "\n")
        return

    session_header = extract_session_header(entries)

    for entry in entries:
        entry["entry_class"] = classify_entry(entry)

    sorted_entries = sort_by_timestamp(entries)

    sorted_entries, cwd_changes = insert_cwd_changes(sorted_entries)

    if simplify:
        if os.path.exists(CONFIG_PATH):
            config = load_config(CONFIG_PATH)
            if truncate:
                config["truncate_enabled"] = True
                logger.info("truncation 已启用")
            else:
                config["truncate_enabled"] = False
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            sorted_entries = simplify_entries(sorted_entries, CONFIG_PATH)
            logger.info("已根据配置精简字段")
        else:
            logger.warning(f"配置文件不存在: {CONFIG_PATH}，跳过精简")

    header_line = {
        "session": session_header,
        "cwdChanges": cwd_changes,
    }
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(header_line, ensure_ascii=False) + "\n")
        for entry in sorted_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info(
        f"处理完成：{len(sorted_entries)} 条 entry（cwd 变化 {cwd_changes} 处）已写入 {output_file}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Session 处理脚本（v3）：分类、排序、精简、session header + cwd_change 插入"
    )
    parser.add_argument("input_file", help="输入文件路径")
    parser.add_argument("output_file", help="输出文件路径")
    parser.add_argument("--no-simplify", action="store_true", help="禁用字段精简")
    parser.add_argument("--truncate", action="store_true", help="启用 truncation 规则（默认关闭）")
    args = parser.parse_args()

    process_session(args.input_file, args.output_file, simplify=not args.no_simplify, truncate=args.truncate)


if __name__ == "__main__":
    main()