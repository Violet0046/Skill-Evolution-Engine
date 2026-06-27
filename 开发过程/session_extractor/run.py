#!/usr/bin/env python3
"""v4 collector 主入口 — argparse + 调 pipeline.run()。

CLI：
  python3 run.py <input> <output>
      [--no-simplify]              禁用字段精简
      [--truncate | --no-truncate] 显式控制 truncation（默认 ON）
      [--no-detectors]             跳过所有 detector（v3 行为）
      [--detector X]               仅启用指定 detector（可多次传）
      [--spec-dir Y]               agent_spec YAML 目录
      [--write-config-defaults]    一次性把 truncate_enabled=true 写回 config
      [--quiet]
"""

import argparse
import json
import logging
import os
import sys

from src.pipeline import run as pipeline_run


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "src", "simplify", "entry_fields_config.json")


def write_config_defaults(config_path: str) -> None:
    """一次性把 entry_fields_config.json 的 truncate_enabled 写回 true。"""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["truncate_enabled"] = True
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    logger.info(f"已把 {config_path} 的 truncate_enabled 写回 true")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="v4 collector：分类 + 精简 + 5 类 detector + 分层结构化证据包"
    )
    parser.add_argument("input_file", help="输入 session JSONL/JSON-array 路径")
    parser.add_argument("output_file", help="输出 v4 evidence bundle JSONL 路径")
    parser.add_argument("--no-simplify", action="store_true", help="禁用字段精简")
    parser.add_argument("--truncate", action="store_true", default=None,
                        help="显式启用 truncation（默认即开启）")
    parser.add_argument("--no-truncate", action="store_true", help="显式关闭 truncation")
    parser.add_argument("--no-detectors", action="store_true", help="跳过所有 detector")
    parser.add_argument("--detector", action="append", default=[],
                        help="仅启用指定 detector（可多次传）")
    parser.add_argument("--spec-dir", default=None, help="agent_spec YAML 目录")
    parser.add_argument("--write-config-defaults", action="store_true",
                        help="一次性把 truncate_enabled=true 写回 config")
    parser.add_argument("--quiet", action="store_true", help="静默模式")
    args = parser.parse_args()

    if args.write_config_defaults:
        write_config_defaults(CONFIG_PATH)
        return 0

    # truncate 参数归一
    if args.no_truncate:
        truncate_flag: "bool | None" = False
    elif args.truncate:
        truncate_flag = True
    else:
        truncate_flag = None  # 用 config 默认值

    enabled_detectors = args.detector if args.detector else None

    pipeline_run(
        input_path=args.input_file,
        output_path=args.output_file,
        config_path=CONFIG_PATH if not args.no_simplify else None,
        spec_dir=args.spec_dir,
        simplify=not args.no_simplify,
        truncate=truncate_flag,
        enabled_detectors=enabled_detectors,
        skip_detectors=args.no_detectors,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())