#!/usr/bin/env python3
"""
分类器覆盖率测试脚本

遍历指定目录下的所有JSONL文件，测试分类器是否能覆盖所有entry类型。
未覆盖的entry会输出到errentry.jsonl文件。

用法：
    python3.8 test_coverage.py                       # 默认测试 ../projects
    python3.8 test_coverage.py <目录>                # 测试指定目录
    python3.8 test_coverage.py --list                # 列出待测文件，不运行
    python3.8 test_coverage.py --output err.jsonl    # 自定义错误输出文件
    python3.8 test_coverage.py --quiet               # 仅输出统计结果
"""

import argparse
import sys
import os
import json
import logging
from pathlib import Path
from collections import Counter

# 添加脚本所在目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.simplify.classifier import classify_entry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# 默认待测目录（脚本所在目录的同级 ../projects）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEST_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "projects"))
DEFAULT_ERROR_FILE = os.path.join(SCRIPT_DIR, "errentry.jsonl")


def find_jsonl_files(directory: str) -> list:
    """查找目录下的所有JSONL文件"""
    jsonl_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".jsonl"):
                jsonl_files.append(os.path.join(root, file))
    return sorted(jsonl_files)


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


def test_classifier_on_file(file_path: str, error_entries: list) -> Counter:
    """测试单个文件中所有entry的分类。返回分类统计 Counter。"""
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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="测试分类器对指定目录下 session entry 的覆盖率",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 test_coverage.py                       # 默认测试 ../projects\n"
            "  python3 test_coverage.py ../projects           # 等价于上面\n"
            "  python3 test_coverage.py --list                # 仅列出待处理文件\n"
            "  python3 test_coverage.py --output err.jsonl    # 自定义错误输出文件\n"
            "  python3 test_coverage.py --quiet               # 仅打印最终统计\n"
        ),
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=DEFAULT_TEST_DIR,
        help=f"待测 session 目录（默认：{DEFAULT_TEST_DIR}）",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_ERROR_FILE,
        help=f"未覆盖 entry 输出文件（默认：{DEFAULT_ERROR_FILE}）",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="仅列出待处理 JSONL 文件，不执行测试",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式，仅打印最终统计结果",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    sessions_dir = os.path.abspath(args.directory)
    if not os.path.isdir(sessions_dir):
        logger.error(f"目录不存在: {sessions_dir}")
        return 1

    jsonl_files = find_jsonl_files(sessions_dir)
    logger.info(f"待测目录: {sessions_dir}")
    logger.info(f"找到 {len(jsonl_files)} 个 JSONL 文件")

    if not jsonl_files:
        logger.warning("目录中没有任何 .jsonl 文件，请检查路径或先把 session 数据放到该目录")
        return 1

    # --list 模式：仅列出文件就退出
    if args.list:
        for f in jsonl_files:
            print(f)
        return 0

    # 统计
    total_entries = 0
    total_classes: Counter = Counter()
    error_entries: list = []

    for file_path in jsonl_files:
        logger.info(f"处理: {file_path}")
        classes = test_classifier_on_file(file_path, error_entries)
        total_classes += classes
        total_entries += sum(classes.values())

    # 输出统计结果
    logger.info("=" * 60)
    logger.info("处理完成：")
    logger.info(f"  文件数量: {len(jsonl_files)}")
    logger.info(f"  总 entry 数: {total_entries}")
    logger.info(f"  未覆盖 entry 数: {len(error_entries)}")
    logger.info("")
    logger.info("分类统计：")
    for cls, count in total_classes.most_common():
        if cls is None:
            logger.info(f"  未覆盖: {count}")
        else:
            logger.info(f"  {cls}: {count}")

    # 保存未覆盖的 entry
    if error_entries:
        error_file = os.path.abspath(args.output)
        with open(error_file, "w", encoding="utf-8") as f:
            for entry in error_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"\n未覆盖的 entry 已保存到: {error_file}")

        error_types = Counter(entry.get("type") for entry in error_entries)
        logger.info("未覆盖 entry 的 type 分布：")
        for type_name, count in error_types.most_common():
            logger.info(f"  {type_name}: {count}")
    else:
        logger.info("\n所有 entry 都已被分类器覆盖！")

    return 0 if not error_entries else 2


if __name__ == "__main__":
    sys.exit(main())