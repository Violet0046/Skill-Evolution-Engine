"""
Entry 精简器

- 按 entry_class 路由配置
- 黑名单：拷贝 entry 全部字段，按 drop 列表删除
- attachment subtype：仅配置的 4 类（hook_success / async_hook_response /
  hook_blocking_error / hook_non_blocking_error）命中；其他 subtype 整类型 DROP
- 整类型 DROP（classifier 返回的 entry_class 不在 config 中）→ 整条丢
- `_META._TRUNCATE` 仅在 `config["truncate_enabled"]` 为真时生效
- 强制保留 `entry_class`（attachment 细化为 attachment.{subtype}）

drop 黑名单模式 — 新字段默认保留，detector 可灵活读取。
"""

import copy
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_config_block(entry: Dict[str, Any], config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """按 entry_class 取配置块。

    - entry_class == "attachment" → attachment.{subtype} 路径
    - 其他 entry_class → 直接查 config 顶层 key
    - 未命中 → 返回 None（整类型 DROP）

    """
    cls = entry.get("entry_class")
    if cls == "attachment":
        att_type = entry.get("attachment", {}).get("type")
        if att_type:
            sub_key = f"attachment.{att_type}"
            if sub_key in config:
                return config[sub_key]
        return None
    if cls and cls in config:
        return config[cls]
    return None


def _iter_path_steps(path: str) -> List[Tuple[str, Optional[int], bool]]:
    """把 `a.b[*].c[2]` 解析成步骤列表。每步 (key, index_or_None, is_wildcard)。"""
    steps: List[Tuple[str, Optional[int], bool]] = []
    for token in path.split("."):
        if not token:
            continue
        is_wildcard = False
        index: Optional[int] = None
        if token.endswith("[*]"):
            key = token[:-3]
            is_wildcard = True
        elif "[" in token and token.endswith("]"):
            key, idx_str = token[:-1].split("[", 1)
            try:
                index = int(idx_str)
            except ValueError:
                key = token
        else:
            key = token
        steps.append((key, index, is_wildcard))
    return steps


def _get_path(node: Any, path: str) -> List[Any]:
    """按路径取出所有命中值（list 通配时展平）。路径不存在返回 []。"""
    steps = _iter_path_steps(path)
    if not steps:
        return [node]

    results: List[Any] = [node]
    for key, index, is_wildcard in steps:
        next_results: List[Any] = []
        for cur in results:
            if not isinstance(cur, dict) or key not in cur:
                continue
            child = cur[key]
            if is_wildcard and isinstance(child, list):
                next_results.extend(child)
            elif index is not None and isinstance(child, list):
                if 0 <= index < len(child):
                    next_results.append(child[index])
            else:
                next_results.append(child)
        results = next_results
        if not results:
            break
    return results


def _set_path(node: Dict[str, Any], path: str, value: Any) -> None:
    """按路径写入值；`[*]` 时为每个 list 元素各自写入子键。"""
    steps = _iter_path_steps(path)
    if not steps:
        return

    def _write(cur: Any, idx: int) -> None:
        if idx >= len(steps):
            return
        key, _index, is_wildcard = steps[idx]
        if idx == len(steps) - 1:
            if isinstance(cur, dict):
                cur[key] = value
            return
        if not isinstance(cur, dict):
            return
        child = cur.get(key)
        if is_wildcard:
            if child is None:
                return
            if not isinstance(child, list):
                return
            for item in child:
                _write(item, idx + 1)
            return
        if not isinstance(child, dict):
            if child is None:
                child = {}
                cur[key] = child
            else:
                return
        _write(child, idx + 1)

    _write(node, 0)


def _strip_wildcard(path: str) -> str:
    """返回 wildcard 步骤之前（含 wildcard 步骤）的容器路径。

    例：`message.content[*].type` → `message.content`
    """
    parts: List[str] = []
    for key, _index, is_wildcard in _iter_path_steps(path):
        parts.append(key)
        if is_wildcard:
            break
    return ".".join(parts)


def _delete_path(node: Any, path: str) -> None:
    """按路径删除字段（含 [*] 通配：每个 list 元素都删 leaf key）。"""
    steps = _iter_path_steps(path)
    if not steps:
        return

    def _walk(cur: Any, idx: int) -> None:
        if not isinstance(cur, dict):
            return
        if idx >= len(steps):
            return
        key, _index, is_wildcard = steps[idx]
        if idx == len(steps) - 1:
            if is_wildcard and key not in cur:
                return
            if is_wildcard:
                children = cur.get(key)
                if isinstance(children, list):
                    for item in children:
                        if isinstance(item, dict):
                            for leaf_step in steps[idx + 1:]:
                                lk = leaf_step[0]
                                if lk in item:
                                    del item[lk]
                return
            cur.pop(key, None)
            return
        child = cur.get(key)
        if is_wildcard and isinstance(child, list):
            for item in child:
                _walk(item, idx + 1)
            return
        if isinstance(child, dict):
            _walk(child, idx + 1)

    _walk(node, 0)


def _truncate_str(value: Any, rule: Dict[str, Any], is_error: bool) -> Any:
    """按 _TRUNCATE 规则截断字符串。非字符串原样返回。"""
    if not isinstance(value, str):
        return value
    if rule.get("keep_whole_if_is_error") and is_error:
        return value
    head = rule.get("max_head")
    tail = rule.get("max_tail")
    marker = rule.get("marker", "\n…[truncated, {n} bytes omitted]…\n")
    if head is None or tail is None:
        return value
    encoded = value.encode("utf-8")
    if len(encoded) <= head + tail:
        return value
    head_bytes = encoded[:head]
    tail_bytes = encoded[-tail:] if tail > 0 else b""
    truncated_marker = marker.format(n=len(encoded) - head - tail).encode("utf-8")
    try:
        return head_bytes.decode("utf-8", errors="ignore") + truncated_marker.decode("utf-8") + tail_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return value


def simplify_entry(entry: Dict[str, Any], config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """精简单条 entry（黑名单模式）。

    返回 None 表示整类型 DROP（不进入输出）；否则返回精简后的 dict。

    步骤：
    1. 取配置块（v3: attachment 仅 hook_success 命中；未命中 → 整类型 DROP）。
    2. 深拷贝 entry → simplified（保留所有原字段）。
    3. 应用 drop 列表（删除指定路径，含通配符）。
    4. 应用 _META._TRUNCATE（仅当 config["truncate_enabled"] 为真）。
    5. 强制保留 entry_class（attachment 细化为 attachment.{subtype}）。
    """
    type_config = _resolve_config_block(entry, config)
    if type_config is None:
        return None

    # 1) 深拷贝 entry → simplified（默认保留所有字段）
    simplified = copy.deepcopy(entry)

    # 2) 应用 drop 列表（黑名单：删除指定路径）
    for drop_path in type_config.get("drop", []):
        _delete_path(simplified, drop_path)

    # 3) 应用 truncation 规则（如果启用）
    if config.get("truncate_enabled"):
        _apply_truncation_rules(
            simplified,
            config.get("_META", {}).get("_TRUNCATE", []),
        )

    # 4) 强制保留 entry_class（attachment 细化为 attachment.{subtype}）
    cls = entry.get("entry_class")
    if cls == "attachment":
        att_type = (entry.get("attachment") or {}).get("type")
        if att_type:
            cls = f"attachment.{att_type}"
    simplified["entry_class"] = cls

    return simplified


def _apply_truncation_rules(entry: Dict[str, Any], rules: List[Dict[str, Any]]) -> None:
    """原地按 rules 截断 entry 的指定路径。

    支持两种路径：
    - 简单路径（无 [*]）：直接取 value → 截断 → 写回
    - 通配路径（含 [*]）：遍历 list 元素，截断 leaf key
    """
    for rule in rules:
        path = rule["path"]
        if "[*]" not in path:
            # 简单路径
            vals = _get_path(entry, path)
            if vals and isinstance(vals[0], str):
                _set_path(entry, path, _truncate_str(vals[0], rule, False))
            continue

        # 通配路径：遍历 list 截断 leaf
        container = _strip_wildcard(path)
        leaf_key = path.rsplit(".", 1)[-1].split("[")[0]
        container_values = _get_path(entry, container)
        if not container_values:
            continue
        for v in container_values:
            if not isinstance(v, list):
                continue
            for item in v:
                if not isinstance(item, dict) or leaf_key not in item:
                    continue
                val = item[leaf_key]
                is_err = bool(item.get("is_error"))
                if leaf_key == "content":
                    empty_marker = rule.get("empty_marker")
                    if val in (None, ""):
                        if empty_marker:
                            item[leaf_key] = empty_marker
                        continue
                item[leaf_key] = _truncate_str(val, rule, is_err)


def simplify_entries(entries: List[Dict[str, Any]], config_path: str) -> List[Dict[str, Any]]:
    """批量精简 entries。整类型 DROP 的 entry（simplify_entry 返回 None）被过滤掉。"""
    config = load_config(config_path)
    out: List[Dict[str, Any]] = []
    dropped = 0
    for entry in entries:
        result = simplify_entry(entry, config)
        if result is None:
            dropped += 1
            continue
        out.append(result)
    logger.info("已精简 %d 个 entries（整类型 DROP %d 条）", len(entries), dropped)
    return out