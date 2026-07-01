"""agent_meta —— subagent 元数据文件 IO。

背景：
  Claude Code session 目录下，每个 subagent 都有一个
  `<sid>/subagents/agent-<id>.meta.json`，含
    {
      "agentType": "差分场景检查单-agent",   // subagent 角色
      "description": "执行差分场景检查单",    // 简短说明
      "toolUseId": "call_xxx"                // 父级 Agent 调用的 tool_use_id
    }

  这些 meta.json 是 subagent 的**角色元数据**，是 subagent 文件本身
  不携带的关键信息（subagent .jsonl 里 attributionSkill=null），
  对 LLM 失败分析按 agentType 分组是**必不可少**的。

公开 API：
  - load_agent_meta(root, session_id)
      → Dict[agent_id, {agentType, description, toolUseId}]

  - copy_agent_meta_files(input_sub_dir, output_sub_dir)
      → int  (拷贝的文件数)
      用于 simplify / ETL 阶段把 meta.json 一并搬运到目标目录。

  - read_agent_meta_file(meta_path)
      → Optional[Dict]  (单个文件读取，容错版)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def read_agent_meta_file(meta_path: Path) -> Optional[Dict[str, Any]]:
    """读单个 meta.json，解析失败返 None。"""
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.warning(f"meta.json 解析失败: {meta_path}, {e}")
    return None


def load_agent_meta(root: str, session_id: str) -> Dict[str, Dict[str, Any]]:
    """加载 session 下所有 subagent 的 meta.json。

    参数：
        root:        数据根目录（含 <sid>/subagents/agent-*.jsonl）
        session_id:  session UUID

    返回：
        Dict[agent_id, meta_dict]
        agent_id 是从文件名 `agent-<id>.meta.json` 提取的 `<id>`。
        目录不存在或无 meta 文件时返空 dict。
    """
    sub_dir = Path(root) / session_id / "subagents"
    if not sub_dir.is_dir():
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for meta_path in sub_dir.glob("agent-*.meta.json"):
        # agent-a1b2c3d4e5f6g7h8.meta.json → a1b2c3d4e5f6g7h8
        agent_id = meta_path.stem.replace("agent-", "", 1).replace(".meta", "", 1)
        data = read_agent_meta_file(meta_path)
        if data is not None:
            result[agent_id] = data
    return result


def copy_agent_meta_files(
    input_sub_dir: Path, output_sub_dir: Path,
) -> int:
    """把 subagents/*.meta.json 整体拷贝到目标目录（内容不变）。

    用途：simplify / ETL 阶段，让元数据跟随主数据一起搬运。
    meta.json 是 SDK 写入的，内容稳定，直接 copy 即可。

    返回：实际拷贝的文件数（0 = 源目录不存在或无 meta 文件）。
    """
    if not input_sub_dir.is_dir():
        return 0
    output_sub_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for meta_path in input_sub_dir.glob("agent-*.meta.json"):
        target = output_sub_dir / meta_path.name
        target.write_text(meta_path.read_text(encoding="utf-8"), encoding="utf-8")
        count += 1
    return count
