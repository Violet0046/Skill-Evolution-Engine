"""
review_db._stash — 阶段 3 dispatch-time 与 post-scan 之间的桥梁

sub-agent 是 run_in_background=true 跑的:
  - see-evolve.py dispatch 后, .change 文件尚未出现, 主进程也已退出
  - 主 agent 在所有 background 完成后另起 see-evolve-finalize.py
  - finalize 必须能拿到当时 dispatch 的 suggestions_json

因此 stash 不能只放内存. 这里:
  - record() 把 (run_id, subject_target) -> {suggestions_json, original_content} 写到
    evidence/<run_id>/.dispatch_stash.json  (每次写都覆盖文件, 用 locking)
  - load_and_clear(run_id) 读出 dict 后删除文件
  - 若文件不存在, 返回 {}  (即 finalize 时拿不到 suggestions 是允许的, 列存空)

文件存在性 self-check 保证幂等.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)


def _stash_path(evidence_root: Path, run_id: str) -> Path:
    """evidence/<run_id>/.dispatch_stash.json"""
    return evidence_root / run_id / ".dispatch_stash.json"


def record(
    evidence_root: Path,
    run_id: str,
    subject_target: str,
    suggestions: list,
    original_content: str,
) -> None:
    """追加一条 dispatch 记录. 失败仅 warn, 不阻塞调用方."""
    p = _stash_path(evidence_root, run_id)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # 读已有 dict (若无则 {})
        existing: dict = {}
        if p.is_file():
            try:
                existing = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        existing[subject_target] = {
            "suggestions_json": suggestions,
            "original_content": original_content,
        }
        # 原子写: 临时文件 + os.replace
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".dispatch_stash.", suffix=".json.tmp", dir=p.parent,
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, p)
        except Exception:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise
    except Exception as e:
        _logger.debug(f"review_db stash.record failed: {e}")


def load_and_clear(evidence_root: Path, run_id: str) -> dict:
    """读出并删除 .dispatch_stash.json. 返回 dict[subject_target, {...}]."""
    p = _stash_path(evidence_root, run_id)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        _logger.debug(f"review_db stash read failed: {e}")
        return {}
    try:
        p.unlink()
    except Exception as e:
        _logger.debug(f"review_db stash delete failed: {e}")
    return data
