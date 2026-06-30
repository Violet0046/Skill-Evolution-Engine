"""simplify/ 子目录：entry 字段精简 + truncation。

- simplifier.py:          字段白名单 + truncate 规则实现
- entry_fields_config.json: 字段保留规范 + truncation 默认配置

"""

from .simplifier import (
    load_config,
    simplify_entry,
    simplify_entries,
    _get_path,
    _set_path,
    _strip_wildcard,
    _iter_path_steps,
    _truncate_str,
)

__all__ = [
    "load_config",
    "simplify_entry",
    "simplify_entries",
    "_get_path",
    "_set_path",
    "_strip_wildcard",
    "_iter_path_steps",
    "_truncate_str",
]
