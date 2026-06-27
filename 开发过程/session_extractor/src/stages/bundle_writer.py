"""bundle_writer stage — make_empty_bundle 兜底 + write_bundle 写 header + NDJSON trace。

header 第 1 行 = bundle.to_dict() 后 pop trace（避免冗余）。
第 2+ 行 = NDJSON trace entries。

"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from src.util.session_io import SESSION_HEADER_FIELDS
from src.models import EvidenceBundle


def make_empty_bundle() -> EvidenceBundle:
    """空输入时返回的 EvidenceBundle（schema_version=4.0）。"""
    return EvidenceBundle(
        schema_version="4.0",
        session={f: None for f in SESSION_HEADER_FIELDS},
        cwd_changes=0,
        trace=[],
        state_machine={"phases": [], "transitions": [], "unexpected_exits": []},
        constraint_events=[],
        user_feedback=[],
        execution_pattern={
            "step_counts": {}, "retry_loops": [],
            "tool_distribution": {}, "phase_durations": {},
        },
        detector_meta={
            "enabled": [], "spec_loaded": False,
            "truncate_enabled": False, "warnings": [],
        },
    )


def write_bundle(
    output_path: str,
    bundle: EvidenceBundle,
    trace: List[Dict[str, Any]],
) -> None:
    """写出第 1 行 header + 后续 NDJSON trace。

    header 不含 trace（避免冗余 — trace 已在 NDJSON 第 2+ 行）。
    """
    bundle_dict = bundle.to_dict()
    # 删除 header 中的 trace（避免冗余 — trace 已写在 NDJSON 第 2+ 行）
    bundle_dict.pop("trace", None)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(bundle_dict, ensure_ascii=False) + "\n")
        for entry in trace:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")