"""
see-collect.py — 遍历 projects/ 下所有 session，仅 simplify 阶段后写到 projects-simplified/。

为 Skill Evolution Engine 提供简化的 session 证据数据
load → classify → simplify → 写 NDJSON。

仅向 stdout 输出一条 JSON 摘要——模型可直接解析。

用法：
  python3.8 infra/scripts/see-collect.py                         # 默认 ../projects → ../projects-simplified
  python3.8 infra/scripts/see-collect.py <projects_dir> <out>   # 自定义输入/输出

stdout JSON 返回结构：
{
  "status": "success" | "partial" | "error",
  "input_dir":  "<str: 解析后的输入目录绝对路径>",
  "output_dir": "<str: 解析后的输出目录绝对路径>",
  "totals": {
    "files_total":    <int: 发现的 .jsonl 文件总数>,
    "files_failed":   <int: 处理失败的文件数；0 表示全部成功>,
    "size_in_bytes":  <int: 输入总体积（仅成功文件）>",
    "size_out_bytes": <int: 输出总体积（仅成功文件）>",
    "entries_in":     <int: 输入总 entry 数（仅成功文件）>",
    "entries_out":    <int: 输出总 entry 数（仅成功文件）>"
  },
  "failed_sessions": [
    "<str: 失败文件的相对路径，仅失败时列出>"
  ]
}

status 含义：
- "success": 所有文件处理成功（files_failed == 0）
- "partial": 部分文件失败（0 < files_failed < files_total）
- "error":   致命错误（输入目录不存在 / 无 .jsonl / 全部失败）

退出码：0 = success 或 partial，1 = error
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 让 `from core.xxx import yyy` 能找到 `infra/core/`
_ROOT = Path(__file__).resolve().parents[2]            # .../Skill-Evolution-Engine
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))

from core.util.session_io import (  # noqa: E402
    load_session_entries,
    extract_session_header,
)
from core.util.agent_meta import copy_agent_meta_files  # noqa: E402
from core.simplify.classifier import classify_entry  # noqa: E402
from core.simplify.simplifier import simplify_entries  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent                    # infra/scripts → 项目根
DEFAULT_PROJECTS_DIR = PROJECT_ROOT / "evidence" / "projects"
CONFIG_PATH = SCRIPT_DIR.parent / "core" / "simplify" / "entry_fields_config.json"


def _make_run_id() -> str:
    """本次运行 run_id（当前时间戳 YYYY-MM-DD-HHMMSS）。"""
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def default_output_dir(run_id: str) -> Path:
    """本次 run 的默认输出目录 = evidence/<run_id>/projects-simplified/。"""
    return PROJECT_ROOT / "evidence" / run_id / "projects-simplified"


def process_one_session(
    input_path: Path,
    output_path: Path,
    projects_dir: Path,
) -> dict:
    """处理单个 session：仅 simplify。返回单 session 摘要（含 input / size_in_bytes / entries / error 等）。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rel_input = str(input_path.relative_to(projects_dir.parent))
    file_type = "sub" if "subagents" in str(input_path) else "main"

    base = {
        "input": rel_input,
        "type": file_type,
        "size_in_bytes": input_path.stat().st_size,
    }

    # 1) 加载（自适应 NDJSON / JSON-array）
    entries, fmt = load_session_entries(str(input_path))
    if not entries:
        return {
            **base,
            "size_out_bytes": 0,
            "entries_in": 0,
            "entries_out": 0,
            "format": fmt,
            "session_id": None,
            "error": "no entries loaded",
        }

    # 2) 提取 session header（slug / sessionId / cwd 等）
    header = extract_session_header(entries)

    # 3) 标 entry_class（pipeline 内部步骤，单文件复用）
    for e in entries:
        e["entry_class"] = classify_entry(e)

    # 4) 简化（应用 config 的 drop / _DROP_CLASSES / _TRUNCATE）
    simplified = simplify_entries(entries, str(CONFIG_PATH))

    # 5) 写出 NDJSON：第 1 行 header，第 2+ 行 simplified entries
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"session": header}, ensure_ascii=False) + "\n")
        for e in simplified:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # 6) 顺手 copy subagents/*.meta.json（让索引构建能拿到 agentType）
    #   主流程：input_path = projects/<sid>.jsonl,  subagents 在 projects/<sid>/subagents/
    #   subagent：input_path = projects/<sid>/subagents/agent-xxx.jsonl, input_path.parent 就是 subagents/
    if file_type == "main":
        sid = header.get("sessionId")
        input_sub_dir = input_path.parent / sid / "subagents" if sid else None
        output_sub_dir = output_path.parent / sid / "subagents" if sid else None
    else:
        input_sub_dir = input_path.parent
        output_sub_dir = output_path.parent
    meta_copied = copy_agent_meta_files(input_sub_dir, output_sub_dir) if input_sub_dir else 0

    size_out = output_path.stat().st_size if output_path.exists() else 0
    result = {
        **base,
        "size_out_bytes": size_out,
        "entries_in": len(entries),
        "entries_out": len(simplified),
        "format": fmt,
        "session_id": header.get("sessionId"),
    }
    if meta_copied:
        result["meta_files_copied"] = meta_copied
    return result


def build_summary_json(
    projects_dir: Path,
    output_dir: Path,
    sessions: list,
    run_id: str | None = None,
    error: str | None = None,
) -> dict:
    """汇总 sessions 列表为最终 stdout JSON 结构。

    - 成功的 session 只计入 totals
    - 失败的 session 同时计入 files_failed 与 failed_sessions[]
    - run_id 透传进顶层（阶段 2/3 用它定位同一 run 的产物）
    """
    files_total = len(sessions)
    files_failed_list = [s for s in sessions if "error" in s]
    files_failed = len(files_failed_list)
    files_success = files_total - files_failed

    if error:
        status = "error"
    elif files_failed == 0:
        status = "success"
    elif files_success == 0:
        status = "error"
    else:
        status = "partial"

    # 只对成功的 session 累加 size/entries
    ok = [s for s in sessions if "error" not in s]
    total_size_in = sum(s["size_in_bytes"] for s in ok)
    total_size_out = sum(s["size_out_bytes"] for s in ok)
    total_entries_in = sum(s["entries_in"] for s in ok)
    total_entries_out = sum(s["entries_out"] for s in ok)

    # 提取成功的 main session UUIDs（top-level .jsonl，排除 subagents/ 子文件）
    main_ok = [s for s in sessions
               if s.get("type") == "main"
               and "error" not in s
               and s.get("session_id")]
    session_ids = [s["session_id"] for s in main_ok]

    summary = {
        "status": status,
        "run_id": run_id,
        "input_dir": str(projects_dir),
        "output_dir": str(output_dir),
        "totals": {
            "files_total": files_total,
            "files_failed": files_failed,
            "size_in_bytes": total_size_in,
            "size_out_bytes": total_size_out,
            "entries_in": total_entries_in,
            "entries_out": total_entries_out,
        },
        "failed_sessions": [s["input"] for s in files_failed_list],
        "session_ids": session_ids,
    }
    if error:
        summary["error"] = error
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="遍历 projects/ 下 session，仅 simplify 阶段后写到 evidence/<run_id>/projects-simplified/。",
    )
    parser.add_argument(
        "projects_dir",
        nargs="?",
        default=str(DEFAULT_PROJECTS_DIR),
        help=f"输入 session 目录（默认：{DEFAULT_PROJECTS_DIR}）",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,  # 默认在 main() 里按 run_id 算
        help="输出简化结果目录（默认：evidence/<run_id>/projects-simplified/）",
    )
    args = parser.parse_args()

    run_id = _make_run_id()
    projects_dir = Path(args.projects_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else default_output_dir(run_id)

    # 致命错误：目录不存在
    if not projects_dir.is_dir():
        print(json.dumps(build_summary_json(
            projects_dir, output_dir, [],
            run_id=run_id,
            error=f"输入目录不存在: {projects_dir}",
        ), ensure_ascii=False))
        return 1

    jsonl_files = sorted(projects_dir.rglob("*.jsonl"))
    if not jsonl_files:
        print(json.dumps(build_summary_json(
            projects_dir, output_dir, [],
            run_id=run_id,
            error="目录中没有任何 .jsonl 文件",
        ), ensure_ascii=False))
        return 1

    sessions = []
    for input_path in jsonl_files:
        rel_path = input_path.relative_to(projects_dir)
        output_path = output_dir / rel_path
        try:
            sessions.append(process_one_session(input_path, output_path, projects_dir))
        except Exception as e:
            sessions.append({
                "input": str(input_path.relative_to(projects_dir.parent)),
                "type": "sub" if "subagents" in str(input_path) else "main",
                "size_in_bytes": input_path.stat().st_size,
                "size_out_bytes": 0,
                "entries_in": 0,
                "entries_out": 0,
                "format": "unknown",
                "session_id": None,
                "error": f"{type(e).__name__}: {e}",
            })

    # 仅 stdout 输出 JSON
    result = build_summary_json(projects_dir, output_dir, sessions, run_id=run_id)
    print(json.dumps(result, ensure_ascii=False))

    return 0 if result["status"] in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())