"""
resolve_architecture.py —— 从 session_id 定位 agent-architectures/ 下对应 JSON

**给主 agent 用**（不是给 sub-agent）。
主 agent 拿到 session_id 后，调本脚本拿 arch 路径 + 是否存在：
  1. load_main_session(root, session_id) → header.get("cwd") 拿 agent_cwd
  2. agent_cwd basename → "agent-architectures/<basename>.json" 绝对路径
  3. 检查文件是否存在

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh python3.8 -m core.util.resolve_architecture <session_id> --run-id <id>

输出 JSON（stdout）：
{
    "arch_path_abs": "<项目根>/agent-architectures/需求分析Agent.json",
    "exists": true
}

session 没找到或 cwd 为空 → arch_path_abs=null, exists=false。
JSON 文件不存在 → exists=false（主 agent 据此 AskUserQuestion 引导用户建文件）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # infra/core/util/ → 项目根
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))

from core.failure_analyzer.common.session_reader import load_main_session  # noqa: E402
from core.failure_analyzer.failure_overview import _load_agent_cwd  # noqa: E402


def resolve(session_id: str, run_id: str | None) -> dict:
    if not session_id:
        return {"arch_path_abs": None, "exists": False}
    if not run_id:
        print("ERROR: --run-id 必填（从阶段 1 stdout 的 run_id 字段解析得到）",
              file=sys.stderr)
        sys.exit(2)

    # 1) 从 session header 拿 agent_cwd（路径 = evidence/<run_id>/projects-simplified）
    root_path = _ROOT / "evidence" / run_id / "projects-simplified"
    agent_cwd = _load_agent_cwd(str(root_path), session_id)
    if not agent_cwd:
        return {"arch_path_abs": None, "exists": False}

    # 2) 拼 arch 路径
    basename = Path(agent_cwd).name
    arch_path_abs = str(_ROOT / "agent-architectures" / f"{basename}.json")
    return {
        "arch_path_abs": arch_path_abs,
        "exists": Path(arch_path_abs).is_file(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从 session_id 定位 agent-architectures/ 下对应 JSON",
    )
    parser.add_argument("session_id", help="目标 session UUID（替代之前的 agent_cwd）")
    parser.add_argument("--run-id", default=None,
                        help="本次运行 run_id（必填；evidence/<run_id>/projects-simplified 由脚本自动拼）")
    args = parser.parse_args()

    result = resolve(args.session_id, args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("arch_path_abs") else 1


if __name__ == "__main__":
    sys.exit(main())
