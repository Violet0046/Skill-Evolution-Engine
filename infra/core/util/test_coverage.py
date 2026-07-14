#!/usr/bin/env python3
"""
分类器覆盖率测试：找出 simplify 阶段没被分类器认领的 entry。

用法：
    python3 infra/core/util/test_coverage.py <sessions_dir>

< sessions_dir > 下递归找所有 .jsonl；每条 entry 调 classify_entry；
返回 None 的写入同目录下的 errentry.jsonl。
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path

# 让 `infra.core...` 可被 import —— 把引擎根加到 sys.path
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from infra.core.simplify.classifier import classify_entry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("test_coverage")


def iter_entries(path: Path):
    """NDJSON 一行一个；[ … ] 整文件当 JSON 数组；坏行 warning 跳过。"""
    try:
        first = next((ln.strip() for ln in path.open(encoding="utf-8") if ln.strip()), None)
    except StopIteration:
        return
    if first is None:
        return
    with path.open(encoding="utf-8") as f:
        if first.startswith("["):
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                log.error(f"{path}: JSON 数组解析失败：{e}")
                return
            yield from ((entry, idx) for idx, entry in enumerate(data, 1) if isinstance(entry, dict))
            return
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                log.error(f"{path}:{lineno} JSON 解析失败：{e}")
                continue
            if isinstance(entry, dict):
                yield entry, lineno


def scan(path: Path, uncovered: list) -> Counter:
    classes = []
    for entry, lineno in iter_entries(path):
        cls = classify_entry(entry)
        if cls is None:
            entry["_source_file"] = str(path)
            entry["_line_number"] = lineno
            uncovered.append(entry)
            log.warning(f"未覆盖: {path}:{lineno} type={entry.get('type')!r}")
        classes.append(cls)
    return Counter(classes)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1

    sessions_dir = Path(sys.argv[1]).expanduser()
    if not sessions_dir.is_dir():
        log.error(f"目录不存在: {sessions_dir}")
        return 1

    jsonl_files = list(sessions_dir.rglob("*.jsonl"))
    log.info(f"找到 {len(jsonl_files)} 个 .jsonl")

    total = Counter()
    uncovered = []
    for path in jsonl_files:
        log.info(f"处理: {path}")
        total += scan(path, uncovered)

    log.info("=" * 50)
    log.info(f"总 entry: {sum(total.values())}  |  未覆盖: {len(uncovered)}")
    log.info("分类统计：")
    for cls, n in total.most_common():
        log.info(f"  {cls}: {n}")

    if uncovered:
        out = Path(__file__).with_name("errentry.jsonl")
        with out.open("w", encoding="utf-8") as f:
            for e in uncovered:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        log.info(f"未覆盖 entry 已写入: {out}")
        log.info("未覆盖 entry 的 type 分布：")
        for t, n in Counter(e.get("type") for e in uncovered).most_common():
            log.info(f"  {t}: {n}")
    else:
        log.info("✅ 所有 entry 都被分类器覆盖")

    return 0


if __name__ == "__main__":
    sys.exit(main())
