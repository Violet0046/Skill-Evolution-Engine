"""see-analyze.py — 阶段 2 入口（analyzer agent 准备 + 数据预热）

设计：
- 不在 CLI 内调 LLM（LLM 由主 agent 调度，sub-agent 跑）
- CLI 的职责是：
  1. 校验 session 存在
  2. 预热索引（懒构建）
  3. 把分析提示词模板 + 工具 schema 输出为一份「analyzer_bundle.json」
  4. 主 agent 拿到 bundle 后用 Agent 工具调起 analyzer sub-agent

用法：
    PYTHONPATH=infra python infra/scripts/see-analyze.py <session_id> [--root <dir>] [--output <bundle.json>]

输出 JSON 结构（stdout / --output 指定文件）：
{
  "session_id": "...",
  "root": "...",
  "index_ready": true,                      # 索引已预热
  "overview": {...},                        # 已运行 see_failure_overview（预热）
  "analyzer_prompt": "..."                  # 填好的 analyzer-prompt.md
  "tool_schemas": [...]                     # 3 个 see_* tool_use schemas
}

主 agent 拿到 bundle 后：
  Agent(
    type="general-purpose",
    prompt=bundle.analyzer_prompt,
    tools=bundle.tool_schemas,    # Anthropic SDK 格式
  )
  → 跑完后写 analysis_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Windows GBK stdout 兜底：让 ❌ / ✅ / 中文 在 console 也能正常输出
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parents[2]
_INFRA = _ROOT / "infra"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))

from core.failure_analyzer import see_failure_overview  # noqa: E402
from core.failure_analyzer.schemas import TOOL_SCHEMAS  # noqa: E402


PROMPT_PATH = _ROOT / "prompts" / "analyzer-prompt.md"


def _load_prompt(session_id: str) -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"analyzer 提示词不存在: {PROMPT_PATH}")
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{session_id}", session_id)


def build_bundle(session_id: str, root: Optional[str]) -> Dict[str, Any]:
    """构造 analyzer_bundle。"""
    # 1) 校验 + 预热（跑一次 overview 让索引生效）
    overview = see_failure_overview(session_id=session_id, root=root, refresh=False)

    if "error" in overview:
        return {
            "session_id": session_id,
            "root": root or "默认: <项目根>/evidence/projects-simplified",
            "index_ready": False,
            "error": overview["error"],
            "analyzer_prompt": None,
            "tool_schemas": TOOL_SCHEMAS,
        }

    # 2) 填好 prompt
    prompt = _load_prompt(session_id)

    return {
        "session_id": session_id,
        "root": root or "默认: <项目根>/evidence/projects-simplified",
        "index_ready": True,
        "overview_summary": overview.get("summary", {}),
        "overview_top_patterns_count": len(overview.get("top_patterns", [])),
        "analyzer_prompt": prompt,
        "tool_schemas": TOOL_SCHEMAS,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阶段 2 入口：准备 analyzer agent 的 prompt + tool schemas，并预热索引",
    )
    parser.add_argument("session_id", help="目标 session UUID")
    parser.add_argument("--root", default=None, help="简化版数据根目录（可选）")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="bundle 输出文件（默认 stdout）")
    parser.add_argument("--refresh", action="store_true", help="强制重建索引")
    args = parser.parse_args()

    bundle = build_bundle(args.session_id, args.root)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已写入 bundle: {args.output}")
    else:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))

    return 0 if bundle.get("index_ready") else 1


if __name__ == "__main__":
    sys.exit(main())
