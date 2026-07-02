"""
resolve-architecture.py —— 解析 session 的 agent_cwd，定位 agent-architectures/ 下对应 JSON

输入 session_id，输出"该 session 是哪个 agent 项目的" + "应该读哪个 JSON"。

**给主 agent 用**（不是给 sub-agent）。
**不预热索引**，**不调 see_* 工具**——只读 session header 拿 cwd。

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/resolve-architecture.py <session_id> [--root <dir>]

输出 JSON（stdout）：
{
    "session_id": "...",
    "agent_cwd": "/media/.../workspace/需求分析Agent",  # session 启动时的工作目录
    "agent_basename": "需求分析Agent",                  # Path(agent_cwd).name
    "arch_file": "agent-architectures/需求分析Agent.json",       # 相对 cwd
    "arch_path_abs": "<cwd>/agent-architectures/需求分析Agent.json",  # 绝对路径
    "exists": true                                       # arch_path_abs 是否存在
}

找不到 session header / 算不出 cwd → agent_cwd = null，arch_file = null。
JSON 文件不存在 → exists = false（主 agent 据此决定 AskUserQuestion）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))

from core.failure_analyzer.common.session_reader import load_main_session  # noqa: E402


def resolve(session_id: str, root: str) -> dict:
    header, _ = load_main_session(root, session_id)
    agent_cwd = header.get("cwd") if isinstance(header, dict) else None

    if not agent_cwd:
        return {
            "session_id": session_id,
            "agent_cwd": None,
            "agent_basename": None,
            "arch_file": None,
            "arch_path_abs": None,
            "exists": False,
        }

    basename = Path(agent_cwd).name
    arch_file = f"agent-architectures/{basename}.json"
    arch_path_abs = str(_ROOT / arch_file)
    exists = Path(arch_path_abs).is_file()

    return {
        "session_id": session_id,
        "agent_cwd": agent_cwd,
        "agent_basename": basename,
        "arch_file": arch_file,
        "arch_path_abs": arch_path_abs,
        "exists": exists,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从 session header 拿 cwd，定位 agent-architectures/ 下对应 JSON",
    )
    parser.add_argument("session_id", help="目标 session UUID")
    parser.add_argument("--root", default=None,
                        help="简化版数据根目录（默认 <项目根>/evidence/projects-simplified）")
    args = parser.parse_args()

    root = args.root or str(_ROOT / "evidence" / "projects-simplified")
    result = resolve(args.session_id, root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("agent_cwd") else 1


if __name__ == "__main__":
    sys.exit(main())
