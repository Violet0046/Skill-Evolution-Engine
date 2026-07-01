"""
index_store.py —— 失败索引懒构建 + mtime 失效检测。

索引目标：
  提取 session 内的"失败模式 → uuid 列表（带 agent_id 归属）"映射，
  缓存到 `<root>/.index/<session_id>.json`，供 see_* 工具按需查询。

**设计原则：只存"用一次以上"的派生数据。**
  - `by_pattern[*].uuids` 是错误 uuid 的**唯一**权威源
  - uuids 是**三元组** `[{uuid, agent_id, source}]`，LLM 拿到即可判断归属
  - 不存元信息（schema_version / built_at / source_signature）：
    * schema_version 用 mtime 检查替
    * built_at / source_signature 是纯 debug 字段，LLM 不用
  - 不存 by_tool / by_skill / by_phase（by_skill 不可靠，by_tool 可从 pattern 拆出）
  - 不存 by_agent_id / by_agent_type（用 by_pattern 替）
  - 不存 tool_use_chains（用 by_pattern + 时间戳 + uuid 顺序替）

索引 schema（v1.6，uuids 三元组）：
{
  "session_id": "5527b413-...",
  "stats": {
    "total_entries": 2417,
    "total_errors": 27,
    "main_errors": 4,
    "sub_errors": 23,
    "subagent_files": 36
  },
  "by_pattern": {
    "Bash:Exit code 1": {
      "count": 8,
      "uuids": [
        {"uuid": "dbad6dda-...", "agent_id": null,                "agent_type": "main"},
        {"uuid": "61be7587-...", "agent_id": "a1cd7b2c3f94f91b6", "agent_type": "差分场景检查单-agent"}
      ]
    }
  },
  "by_agent_type": {
    "review-agent":            {"errors": 5, "error_uuids": ["..."]},
    "差分场景检查单-agent":    {"errors": 1, "error_uuids": ["..."]},
    "main":                    {"errors": 4, "error_uuids": ["..."]}
  }
}

注：v1.6 删 source 字段，工具输出层按需从 agent_id 推导
   (agent_id=None → "main", else → "subagent")。

失效检测：
  - 任一源文件 mtime > 索引 mtime → 重建
  - 提供 rebuild-index CLI 强制重建

性能（实测 7h / 2,417 entry session）：
  - 首构 ~200-400ms；二次查询 < 5ms
  - 索引文件大小：~5KB（极简后）

工具函数：
  - SessionIndex(session_id, root)         # 主入口
  - SessionIndex.load() -> Dict           # 加载 / 构建
  - SessionIndex.invalidate() -> None     # 强制失效（重建前调用）
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .session_reader import (
    collect_all_entries,
    load_subagent_files,
)
from ...util.agent_meta import load_agent_meta  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部：从 entry 抽取分析所需字段
# ---------------------------------------------------------------------------

def _get_tool_name_from_call(call_entry: Optional[Dict[str, Any]]) -> Optional[str]:
    """从 ai_tool_call entry 提取 tool name（content[0].name）。"""
    if not call_entry:
        return None
    content = call_entry.get("message", {}).get("content", [])
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict):
            return item.get("name")
    return None


def _get_error_first_line(tool_result_entry: Dict[str, Any]) -> str:
    """从 tool_result entry 提取错误首行（80 字符内）。"""
    content = tool_result_entry.get("message", {}).get("content", [])
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict):
            err_text = item.get("content", "") or ""
            if err_text:
                first_line = err_text.split("\n", 1)[0].strip()
                return first_line[:80]
    # fallback 到 toolUseResult 字符串
    tur = tool_result_entry.get("toolUseResult")
    if isinstance(tur, str):
        first_line = tur.split("\n", 1)[0].strip()
        return first_line[:80]
    return ""


def _make_pattern_key(tool_name: str, error_first_line: str) -> str:
    """构造失败模式 key：`<tool_name>:<error[:80]>`。

    与 infra/analyze.py 的 `f"{tool_name}:{error[:80]}"` 保持一致，方便对接。
    """
    return f"{tool_name}:{error_first_line}"


# ---------------------------------------------------------------------------
# 主类：SessionIndex
# ---------------------------------------------------------------------------

class SessionIndex:
    """单个 session 的失败索引（懒构建 + mtime 失效）。"""

    def __init__(self, session_id: str, root: str | None = None):
        self.session_id = session_id
        # 默认根目录：项目根/evidence/projects-simplified
        # 本文件位于 infra/core/failure_analyzer/common/index_store.py
        #   parents[0]=common/  parents[1]=failure_analyzer/  parents[2]=core/
        #   parents[3]=infra/  parents[4]=项目根
        if root is None:
            root = str(Path(__file__).resolve().parents[4] / "evidence" / "projects-simplified")
        self.root = Path(root)
        self.index_path = self.root / ".index" / f"{session_id}.json"
        self._data: Optional[Dict[str, Any]] = None

    # ---------- public ----------

    def load(self) -> Dict[str, Any]:
        """加载索引（必要时构建）。返回索引 dict。"""
        if self._data is not None:
            return self._data
        if self._needs_rebuild():
            self._build()
        with open(self.index_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        return self._data

    def invalidate(self) -> None:
        """强制下次 load 重建索引。"""
        if self.index_path.exists():
            self.index_path.unlink()
        self._data = None

    def exists(self) -> bool:
        """检查索引文件是否存在。"""
        return self.index_path.exists()

    # ---------- internal: 失效检测 ----------

    def _needs_rebuild(self) -> bool:
        """检查源文件是否有变化。"""
        if not self.index_path.exists():
            return True

        idx_mtime = self.index_path.stat().st_mtime
        # 源文件 mtime 任何一个比索引新 → 重建
        for src in self._iter_source_files():
            if src.exists() and src.stat().st_mtime > idx_mtime:
                return True
        return False

    def _iter_source_files(self):
        """迭代所有源文件路径（主+子）。"""
        yield self.root / f"{self.session_id}.jsonl"
        sub_dir = self.root / self.session_id / "subagents"
        if sub_dir.is_dir():
            for f in sub_dir.glob("agent-*.jsonl"):
                yield f

    # ---------- internal: 构建 ----------

    def _build(self) -> None:
        """构建索引并写盘（v1.6：uuids 记录去掉 source 字段）。

        详细构建逻辑：
        1. 加载 subagent meta.json → agent_meta{agent_id: {agentType, ...}}
        2. 一次性扫所有 entry，标 entry_class + 找 ai_tool_call 反查表
        3. 对每个 is_error=true 的 tool_result entry：
           - 找对应 ai_tool_call 取 tool_name
           - 取 error_first_line
           - 拼 pattern key (`{tool_name}:{error[:80]}`)
           - 推导 agent_id / agent_type
           - 追加 `{uuid, agent_id, agent_type}` 到 by_pattern[pattern].uuids
           - 同时累加 by_agent_type 错误数
        4. 同时统计 main / sub 错误数（for stats）

        注：v1.6 删 source 字段（冗余：source=main ↔ agent_id=null，
            source=subagent ↔ agent_id!=null，agent_type 已带语义）。
            工具输出层如需 source，从 agent_id 推导。
        """
        logger.info(f"构建 session 索引: {self.session_id}")
        t0 = time.time()

        # 1) 加载所有 entries + subagent meta.json
        all_entries = collect_all_entries(str(self.root), self.session_id)
        sub_map = load_subagent_files(str(self.root), self.session_id)
        agent_meta = load_agent_meta(str(self.root), self.session_id)

        # 2) 建立 uuid → ai_tool_call 反查（仅扫描 ai_tool_call 类型）
        uuid_to_call: Dict[str, Dict[str, Any]] = {}
        for e in all_entries:
            if e.get("entry_class") == "ai_tool_call":
                u = e.get("uuid")
                if u:
                    uuid_to_call[u] = e

        # 3) 扫 tool_result，错误入 by_pattern（内嵌 agent_type）
        by_pattern: Dict[str, Dict[str, Any]] = {}
        by_agent_type: Dict[str, Dict[str, Any]] = {}
        main_errors = 0
        sub_errors = 0

        for e in all_entries:
            if e.get("entry_class") != "tool_result":
                continue

            # 错误判定
            content = e.get("message", {}).get("content", [])
            is_error = False
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("is_error"):
                        is_error = True
                        break
            if not is_error:
                continue

            # 找对应 ai_tool_call → tool_name
            call_uuid = e.get("sourceToolAssistantUUID")
            call_entry = uuid_to_call.get(call_uuid) if call_uuid else None
            tool_name = _get_tool_name_from_call(call_entry) if call_entry else "Unknown"
            error_first = _get_error_first_line(e)
            pattern = _make_pattern_key(tool_name, error_first)

            # 推导 agent_id / agent_type（v1.6 删 source，工具层按需从 agent_id 推导）
            src_label = e.get("_source", "main")
            if src_label == "main":
                agent_id: Optional[str] = None
                agent_type = "main"
            else:
                agent_id = src_label.split(":", 1)[1]
                agent_type = agent_meta.get(agent_id, {}).get("agentType", "unknown")

            # by_pattern —— 错误 uuid 的唯一权威源（v1.6 三元组：uuid/agent_id/agent_type）
            u = e.get("uuid")
            bucket = by_pattern.setdefault(pattern, {"count": 0, "uuids": []})
            bucket["count"] += 1
            if u:
                bucket["uuids"].append({
                    "uuid": u,
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                })

            # by_agent_type 聚合（v1.5 简化：只统计）
            atype_bucket = by_agent_type.setdefault(agent_type, {
                "errors": 0,
                "error_uuids": [],
            })
            atype_bucket["errors"] += 1
            if u:
                atype_bucket["error_uuids"].append(u)

            # main / sub 错误计数
            if src_label == "main":
                main_errors += 1
            else:
                sub_errors += 1

        # 4) 排序 by_pattern（按 count desc）
        by_pattern_sorted = dict(
            sorted(by_pattern.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
        )

        # 排序 by_agent_type（按 errors desc）
        by_agent_type_sorted = dict(
            sorted(by_agent_type.items(), key=lambda kv: -kv[1]["errors"])
        )

        # 5) 装配索引（v1.5：无 agent_meta；by_agent_type 仅含 errors/error_uuids）
        index_data = {
            "session_id": self.session_id,
            "stats": {
                "total_entries": len(all_entries),
                "total_errors": main_errors + sub_errors,
                "main_errors": main_errors,
                "sub_errors": sub_errors,
                "subagent_files": len(sub_map),
            },
            "by_pattern": by_pattern_sorted,
            "by_agent_type": by_agent_type_sorted,
        }

        # 6) 写盘
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        self._data = index_data
        elapsed = (time.time() - t0) * 1000
        logger.info(
            f"索引构建完成: {self.session_id} | "
            f"entries={len(all_entries)} errors={main_errors + sub_errors} "
            f"patterns={len(by_pattern)} took={elapsed:.0f}ms"
        )

    # ---------- 工具快捷方法 ----------

    def get_pattern_uuids(self, pattern: str) -> List[Dict[str, Any]]:
        """按 pattern key 查 uuid 三元组列表（找不到返 []）。

        每个元素是 {uuid, agent_id, source}。
        """
        data = self.load()
        return list(data.get("by_pattern", {}).get(pattern, {}).get("uuids", []))

    def get_all_error_uuid_records(self) -> List[Dict[str, Any]]:
        """返回所有错误 uuid 记录（from by_pattern[*].uuids 并集）。"""
        data = self.load()
        out: List[Dict[str, Any]] = []
        for info in data.get("by_pattern", {}).values():
            out.extend(info.get("uuids", []))
        return out

    def find_uuid_record(self, uuid: str) -> Optional[Dict[str, Any]]:
        """按 uuid 查错误记录（含 agent_id / source）。

        返回：
            {uuid, agent_id, source} 字典（如 uuid 命中某个 pattern）
            None（如 uuid 不是错误，或 session 内不存在）

        用途：
            给 see_entry_detail 用来直接定位到具体文件，避免扫 36 个 subagent。
            **只覆盖错误 uuid**——非错误 uuid 返 None，调用方需 fallback 全扫。
        """
        for rec in self.get_all_error_uuid_records():
            if rec.get("uuid") == uuid:
                return rec
        return None
