"""
cli.py —— `PYTHONPATH=infra python -m core.failure_analyzer <cmd> <args>` 形式 CLI（Bash 调用入口）

调用风格（<> 必填，[] 可选）：
    overview <session_id> [--refresh] [--top-n-patterns N]
        返回 session 统计 + top-N 失败模式。默认懒构建索引。

    find <session_id> [<pattern>] [--limit N] [--main-only] [--list-patterns]
        按失败模式找 entry。
          不传 pattern / 加 --list-patterns：列出所有 pattern（含 main/subagent 分布）
          传 pattern：搜该 pattern 的所有 hit

    detail <session_id> <uuid> [--use-raw] [--no-reasoning-before] [--no-reasoning-after]
        取单条 entry 完整上下文（5 字段，按 T1→T2→T3→T4 顺序）。

    list
        列出所有可用工具（含每条 help 描述）。

    --help / -h（任意层级）：显示帮助文本
        PYTHONPATH=infra python3 -m core.failure_analyzer --help           # 主 help
        PYTHONPATH=infra python3 -m core.failure_analyzer find --help      # 某子命令详细 help

退出码：
    0 = 成功（含业务错误如 "session not found"）
    1 = 调用方式错误（参数错 / 找不到 tool）

输出：
    stdout: JSON（顶层 dict，UTF-8 编码，ensure_ascii=False）
    stderr: 日志（WARNING/ERROR 由 logger 走默认格式）

设计取舍：
    - 退出码恒为 0（除编程错误）—— LLM 不应该把"session not found"当 fatal
    - 不静默吞错误（与 infra/scripts/see-*.py 一致）
    - 输出紧凑 JSON（indent=2 for human，不压缩 for machine）
    - overview 自动懒构建索引，需要强制重建加 --refresh（替代旧 rebuild-index）
    - find pattern 是**位置参数**（不是 --pattern VALUE），更直观
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("see_tools")


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------

def _print_result(result: Dict[str, Any]) -> int:
    """统一输出：JSON 到 stdout。"""
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_overview(args: argparse.Namespace) -> int:
    """overview 预热 .index/<sid>.json（**不**返 dict，失败 raise）。"""
    from .failure_overview import see_failure_overview
    see_failure_overview(
        session_id=args.session_id,
        root=args.root,
        refresh=args.refresh,
    )
    # 成功：stdout 静默（**不** print "null"）
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    """两种进入方式都按 agent 维度（不再支持按 pattern）：
      1) find <sid>                       — 列出所有 agent（按 count 降序）
      2) find <sid> --agent-type <type>   — 查该 agent 的所有 hit (返回 uuid 列表 + summary)
    """
    from pathlib import Path
    from .common.errors import err as _err
    from .common.index_store import SessionIndex

    root = args.root or str(Path(__file__).resolve().parents[3] / "evidence" / "projects-simplified")
    main_path = Path(root) / f"{args.session_id}.jsonl"
    if not main_path.exists():
        return _print_result(_err(f"session not found: {args.session_id}",
                                   session_id=args.session_id, root=root))
    try:
        idx = SessionIndex(args.session_id, root)
        data = idx.load()
    except Exception as e:
        return _print_result(_err(f"index load failed: {e}", session_id=args.session_id))

    # 不传 --agent-type：列所有 agent
    if not args.agent_type:
        items = [
            {
                "agent_type": atype,
                "count": info.get("count", 0),
            }
            for atype, info in data.get("by_agent_type", {}).items()
        ]
        return _print_result({
            "session_id": args.session_id,
            "agents": items,
            "count": len(items),
            "hint": "复制任一 agent_type 值后用 find <sid> --agent-type <type> 查该 agent 的所有 hit",
        })

    # 传 --agent-type：返回该 agent 的所有 hit uuid + agent_id（sub-agent 用 detail 看具体）
    bucket = data.get("by_agent_type", {}).get(args.agent_type)
    if not bucket:
        return _print_result({
            "session_id": args.session_id,
            "agent_type": args.agent_type,
            "matched": 0,
            "hits": [],
        })

    all_hits = bucket.get("uuids", [])
    if args.main_only:
        all_hits = [h for h in all_hits if h.get("agent_id") is None]
    limited = all_hits[:args.limit]

    return _print_result({
        "session_id": args.session_id,
        "agent_type": args.agent_type,
        "matched": len(all_hits),
        "returned": len(limited),
        "hits": limited,
        "hint": "用 detail <sid> <uuid> 看每个 hit 的完整上下文（T1→T4）",
    })


def cmd_detail(args: argparse.Namespace) -> int:
    from .failure_detail import see_entry_detail
    result = see_entry_detail(
        session_id=args.session_id,
        uuid=args.uuid,
        root=args.root,
        raw_root=args.raw_root,
        use_raw=args.use_raw,
        include_reasoning_before=not args.no_reasoning_before,
        include_reasoning_after=not args.no_reasoning_after,
    )
    return _print_result(result)


def cmd_list(_args: argparse.Namespace) -> int:
    """列出所有可用工具 + 简短描述（用 argparse help= 而非 LLM schema description）。"""
    from .cli import build_parser
    parser = build_parser()
    # 收集子命令的 help 文本
    tools: List[Dict[str, Any]] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                if name in ("list", "help"):
                    continue
                tools.append({
                    "name": name,
                    "help": sub.description or sub.help or "",
                })
    return _print_result({"tools": tools, "count": len(tools)})


# ---------------------------------------------------------------------------
# argparse 装配
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="see-tools",
        description=(
            "see-tools —— 失败分析 LLM 工具集 CLI。\n"
            "4 个子命令：overview / find / detail / list。\n"
            "用法：PYTHONPATH=infra python3 -m core.failure_analyzer <cmd> --help  查看子命令详细帮助。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<cmd>")

    # 全局参数
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=None,
                        help="简化版数据根目录（默认 ../projects-simplified）")

    # overview
    p_ov = sub.add_parser(
        "overview", parents=[common],
        help="获取 session 失败概览（stats + by_agent_type）",
        description=(
            "返回 session 统计（总 entry 数 / 错误数 / 持续时间）+ by_agent_type 聚类（按错误数降序）。\n"
            "默认懒构建索引（首次调用约 200-400ms），加 --refresh 强制重建。"
        ),
    )
    p_ov.add_argument("session_id", help="Session UUID")
    p_ov.add_argument("--refresh", action="store_true",
                      help="强制重建索引（覆盖源文件 mtime 检查）")
    p_ov.set_defaults(func=cmd_overview)

    # find
    p_find = sub.add_parser(
        "find", parents=[common],
        help="按 agent 找 entry（不传 --agent-type 则列出所有 agent）",
        description=(
            "两种用法：\n"
            "  1) find <sid>                        — 列出所有 agent（按 count 降序）\n"
            "  2) find <sid> --agent-type <type>    — 查该 agent 的所有 hit\n"
            "\n"
            "agent_type 通常从 overview 的 by_agent_type[*].agent_type 复制得到"
        ),
    )
    p_find.add_argument("session_id", help="Session UUID")
    p_find.add_argument("--agent-type", default=None,
                        help="按 agent_type 查所有 hit")
    p_find.add_argument("--limit", type=int, default=20, help="返回 hit 上限（默认 20）")
    p_find.add_argument("--main-only", action="store_true",
                        help="仅返回主流程命中（不含 subagent）")
    p_find.set_defaults(func=cmd_find)

    # detail
    p_det = sub.add_parser(
        "detail", parents=[common],
        help="取单条 entry 完整上下文（5 字段，按 T1→T2→T3→T4 顺序）",
        description=(
            "返回 5 字段聚焦失败原因：\n"
            "  reasoning_before (T1)  → 模型事前计划\n"
            "  tool_name        (T2)  → 工具名\n"
            "  input_params     (T2)  → 调用参数\n"
            "  error_output     (T3)  → 失败信息（成功为 null）\n"
            "  reasoning_after  (T4)  → 模型事后归因\n"
            "uuid 通常从 find 的 hits[*].uuid 复制得到"
        ),
    )
    p_det.add_argument("session_id", help="Session UUID")
    p_det.add_argument("uuid", help="目标 entry UUID")
    p_det.add_argument("--raw-root", default=None,
                       help="原始版数据根目录（--use-raw 时使用）")
    p_det.add_argument("--use-raw", action="store_true",
                       help="从原始未 simplify 数据取（拿到完整 toolUseResult）")
    p_det.add_argument("--no-reasoning-before", action="store_true",
                      help="不包含 reasoning_before（模型事前计划）")
    p_det.add_argument("--no-reasoning-after", action="store_true",
                      help="不包含 reasoning_after（模型事后归因）")
    p_det.set_defaults(func=cmd_detail)

    # list
    p_list = sub.add_parser(
        "list", help="列出所有可用工具（人话简短描述）",
        description="列出 see_* 工具的 name + help 描述，用于 discover 工具用法",
    )
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        # 编程错误：参数解析之外的异常
        logger.exception(f"未捕获异常: {e}")
        print(json.dumps({
            "error": f"unexpected: {type(e).__name__}: {e}",
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
