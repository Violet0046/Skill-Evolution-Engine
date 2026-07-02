"""see-analyze.py — 阶段 2 入口（数据预热 + bundle 组装）

设计：
- 不在 CLI 内调 LLM（LLM 由主 agent 调度，sub-agent 跑）
- CLI 的职责是：
  1. 校验 session 存在
  2. 预热索引（懒构建）
  3. 跑一次 see_failure_overview 让索引生效
  4. 输出 analyzer_bundle（session_id + overview + tool_schemas + prompt 路径）
- **不读 prompt 模板**：主 agent 自己 Read `prompts/analyzer-prompt.md` 并拼装 sub-agent prompt

用法：
    PYTHONPATH=infra python infra/scripts/see-analyze.py <session_id> [--root <dir>] [--output <bundle.json>]

输出 JSON 结构（stdout / --output 指定文件）：
{
  "session_id": "...",
  "root": "...",
  "index_ready": true,                      # 索引已预热
  "overview_summary": {...},                # 已运行 see_failure_overview（预热）
  "prompt_template_path": ".../prompts/analyzer-prompt.md",   # 主 agent 自己 Read
  "tool_schemas": [...]                     # 3 个 see_* tool_use schemas
}

主 agent 拿到 bundle 后：
  1. Read bundle.prompt_template_path 拿 prompt 模板
  2. Agent(
       type="general-purpose",
       prompt=<Read 的内容>,
       tools=bundle.tool_schemas,
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


PROMPT_TEMPLATE_PATH = _ROOT / "prompts" / "analyzer-prompt.md"

# analysis_report 输出目录（sub-agent 用 Write 工具写到这里的子路径）
# 跑 see-analyze 时自动 mkdir -p（兜底，避免 sub-agent 写盘时"目录不存在"）
ANALYSIS_REPORTS_DIR = _ROOT / "evidence" / "analysis_reports"


def build_bundle(session_id: str, root: Optional[str]) -> Dict[str, Any]:
    """构造 analyzer_bundle。

    不再读 prompt 模板——主 agent 负责 Read `prompts/analyzer-prompt.md` 并拼装 sub-agent 的 prompt。
    脚本只交付：session_id + overview + tool_schemas + prompt 路径 + report_path。
    """
    # 0) 兜底：确保 evidence/analysis_reports/ 存在（幂等）
    ANALYSIS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 校验 + 预热（跑一次 overview 让索引生效）
    overview = see_failure_overview(session_id=session_id, root=root, refresh=False)

    if "error" in overview:
        return {
            "session_id": session_id,
            "root": root or "默认: <项目根>/evidence/projects-simplified",
            "index_ready": False,
            "error": overview["error"],
            "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
            "report_path": str(ANALYSIS_REPORTS_DIR / f"{session_id}.analysis_report.json"),
            "tool_schemas": TOOL_SCHEMAS,
        }

    return {
        "session_id": session_id,
        "agent_cwd": overview.get("agent_cwd"),
        "root": root or "默认: <项目根>/evidence/projects-simplified",
        "index_ready": True,
        "overview_summary": overview.get("summary", {}),
        "overview_top_patterns_count": len(overview.get("top_patterns", [])),
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
        "report_path": str(ANALYSIS_REPORTS_DIR / f"{session_id}.analysis_report.json"),
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
