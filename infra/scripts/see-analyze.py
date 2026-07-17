"""
see-analyze.py — 阶段 2 入口（**完整** sub-agent prompt 拼装）

设计：
- 不在 CLI 内调 LLM（LLM 由主 agent 调度，sub-agent 跑）
- 主 agent 调一次本脚本 → 拿**完整** sub-agent prompt
- CLI 内部流程：
  1. 跑 see_failure_overview（拿 4 字段 bundle + 写 .index/ 索引，**自然产生**）
  2. 调 core.util.resolve_architecture 拿 arch 路径（用 session_id 算）
  3. 读 prompts/analyzer-prompt.md 模板
  4. 读 rules/analyzer-agent-rules.md 规则
  5. 读 arch JSON
  6. 替换模板中的 7 个占位符（{{RULES}} / {{REPORT_PATH}} / {{AGENT_ARCH}} / {{OVERVIEW_SUMMARY}} / {{SUBJECT_NAME}} / {{SESSION_ID}} / {{RUN_ID}}）
  7. 输出完整 prompt 字符串到 stdout

为什么**拼完整 prompt 在这里**（**不**在主 agent）：
- 主 agent 调 1 次拿**完整** prompt，**不**用自己拼字符串
- 拼装逻辑集中（替换占位符的规则**只**在 see-analyze.py 里）
- 测试简单（直接 stdout 比对）

run_id 隔离（**必传**）：
- `--run-id` 必填——没传直接报错，没有 env fallback / 没有时间戳 fallback
- 简化版数据根目录 = `evidence/<run_id>/projects-simplified`（脚本按 run_id 自动拼）
- `analysis_report.json` 写到 `evidence/<run_id>/analysis_reports/<sid>.analysis_report.json`
- 阶段 1 创建目录后，阶段 2/3 必须用同一个 run_id

用法：
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <session_id> --run-id <id> [--output <prompt.md>]

输出（stdout / --output 指定文件）：完整 sub-agent prompt 字符串
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Windows GBK stdout 兜底
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
from core.util.resolve_architecture import resolve as resolve_architecture  # noqa: E402


PROMPT_TEMPLATE = _ROOT / "prompts" / "analyzer-prompt.md"
RULES_FILE = _ROOT / "rules" / "analyzer-agent-rules.md"


def _run_subprocess(cmd: list[str], env_extra: dict | None = None) -> dict:
    """跑子命令，stdout JSON 解析成 dict。失败抛 RuntimeError。"""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"{cmd[0]} 失败 (exit={result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{cmd[0]} 输出不是 JSON: {e}")


def assemble_prompt(session_id: str, run_id: str) -> str:
    """完整 sub-agent prompt 拼装（输入 session_id + run_id，**不**需要 agent_cwd）。"""
    root = str(_ROOT / "evidence" / run_id / "projects-simplified")

    # 1) overview（写 .index/，失败 raise）
    see_failure_overview(session_id=session_id, root=root, refresh=False)

    # 2) resolve_architecture（用 session_id 拿 arch 路径）
    arch_result = _run_subprocess(
        ["bash", str(_ROOT / "infra/scripts/with-python.sh"),
         "-m", "core.util.resolve_architecture", session_id, "--run-id", run_id],
    )
    arch_path_abs = arch_result.get("arch_path_abs")
    exists = arch_result.get("exists", False)
    if not arch_path_abs or not exists:
        print(f"ERROR: arch 不存在 ({arch_path_abs})", file=sys.stderr)
        sys.exit(1)

    # subject_name = arch 文件名 stem（= cwd basename），阶段 3 用它定位 project_root
    subject_name = Path(arch_path_abs).stem

    # 3) 读模板 + 规则 + arch
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    rules = RULES_FILE.read_text(encoding="utf-8")
    arch_content = Path(arch_path_abs).read_text(encoding="utf-8")

    # 4) 失败概览段（**自己**读 .index/<sid>.json 取 summary + by_agent_type）
    #    —— overview 已写好 .index/，**直接**读（路径在 run_id 下）
    index_data = json.loads(
        (Path(root) / ".index" / f"{session_id}.json")
        .read_text(encoding="utf-8")
    )
    overview_md = _format_overview(index_data)

    # 5) 报告路径（脚本自己算：evidence/<run_id>/analysis_reports/<sid>.json）
    report_path = str(_ROOT / "evidence" / run_id / "analysis_reports" / f"{session_id}.analysis_report.json")

    # 6) 替换模板中的 7 个占位符
    return (template
            .replace("{{RULES}}", rules)
            .replace("{{REPORT_PATH}}", report_path)
            .replace("{{AGENT_ARCH}}", arch_content)
            .replace("{{OVERVIEW_SUMMARY}}", overview_md)
            .replace("{{SUBJECT_NAME}}", subject_name)
            .replace("{{SESSION_ID}}", session_id)
            .replace("{{RUN_ID}}", run_id))


def build_agent_call(session_id: str, run_id: str) -> dict:
    """构造单个 Agent() 调用的 JSON 配置（data-driven dispatch）。

    主 agent 拿这个 JSON 直接当 Agent(...) 调用的参数源——避免主 agent 自己
    选错 subagent_type、忘加 run_in_background、或手写 prompt。

    4 个字段：
    - description: Agent tool 必填
    - subagent_type: 硬编码 "general-purpose"（项目术语"analyzer"是逻辑角色，Agent tool 不接受）
    - run_in_background: 硬编码 True（不阻塞，让主 agent 一次性 fire N 个）
    - prompt: 完整的 analyzer-prompt 文本（assemble_prompt() 产物）
    """
    prompt = assemble_prompt(session_id, run_id)
    return {
        "description": f"Analyze session {session_id}",
        "subagent_type": "general-purpose",
        "run_in_background": True,
        "prompt": prompt,
    }


def _format_overview(bundle: dict) -> str:
    """把 bundle.summary + by_agent_type 格式化成 markdown。

    by_agent_type 支持两种格式：
    - dict（从 .index/ 文件读）：{agent_type: {count, uuids}}
    - list[dict]（从 see_failure_overview return）：[{agent_type, count, uuids}]
    """
    summary = bundle.get("summary", {})
    by_agent_type = bundle.get("by_agent_type", {})

    lines = []
    lines.append("**Summary**: " + json.dumps(summary, ensure_ascii=False))
    if by_agent_type:
        lines.append("")
        lines.append("**By agent type** (按错误数降序):")
        if isinstance(by_agent_type, dict):
            for atype, info in by_agent_type.items():
                lines.append(f"- `{atype}` ×{info.get('count', 0)}")
        else:
            for a in by_agent_type:
                lines.append(f"- `{a.get('agent_type', '?')}` ×{a.get('count', 0)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阶段 2 入口：构造 sub-agent 调用配置（data-driven dispatch JSON）",
    )
    parser.add_argument("session_id", help="目标 session UUID")
    parser.add_argument("--run-id", default=None,
                        help="本次运行的 run_id（必填，从阶段 1 stdout 解析得到）")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="prompt 字段写到文件（默认 stdout 输出 4 字段 JSON）")
    args = parser.parse_args()

    if not args.run_id:
        print("ERROR: --run-id 必填（从阶段 1 stdout 的 run_id 字段解析得到）", file=sys.stderr)
        return 2

    try:
        agent_call = build_agent_call(args.session_id, args.run_id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if args.output:
        # --output 模式：只写 prompt 字段到文件（给人类测试用）
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(agent_call["prompt"], encoding="utf-8")
        print(f"已写入 prompt: {args.output}")
    else:
        # 默认模式：输出 4 字段 JSON（主 agent parse 后直接当 Agent() 参数）
        print(json.dumps(agent_call, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
