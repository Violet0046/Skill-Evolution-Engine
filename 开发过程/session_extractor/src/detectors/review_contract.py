"""
review_contract detector — 识别 review-agent 调用契约违反。

检测项：
1. subagent_type 不匹配 spec 中 expected_subagent_types
2. tool_result 缺少 `passed` / `retryAdvice` 字段
3. retry_count 超过 spec.retry_count

触发条件：
- entry_class == "ai_tool_call"
- message.content[*].name == "Agent"
- subagent_type 含 "review" 子串
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from src.models import ClassifiedEntry, DetectorContext, ReviewContractEvent
from .base import Detector, register


_REVIEW_RE = re.compile(r"review[-_]?agent", re.IGNORECASE)


@register("review_contract")
class ReviewContractDetector(Detector):
    """review-agent 契约违反检测。"""

    def run(
        self,
        entries: List[ClassifiedEntry],
        ctx: DetectorContext,
    ) -> List[Dict[str, Any]]:
        spec_review = (ctx.spec.get("subagents") or {}).get("review-agent", {}) if isinstance(ctx.spec, dict) else {}
        has_spec = bool(spec_review)
        expected_types = spec_review.get("expected_subagent_types") or []
        max_retries = int(spec_review.get("retry_count") or 0)
        # required_fields 缺省 = 空 list（spec 缺省时不查 missing field）
        required_fields = spec_review.get("required_fields") or []

        out: List[ReviewContractEvent] = []

        # 收集所有 review-agent 调用
        review_calls: List[tuple] = []  # (entry, tool_use_id, sub_type, idx_in_entries)
        for i, e in enumerate(entries):
            if e.entry_class != "ai_tool_call":
                continue
            content = (e.raw.get("message", {}) or {}).get("content", []) or []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("name") != "Agent":
                    continue
                sub_type = item.get("input", {}).get("subagent_type", "")
                if not isinstance(sub_type, str) or not _REVIEW_RE.search(sub_type):
                    continue
                review_calls.append((e, item.get("id", ""), sub_type, i))

        # spec 缺省 → 无任何检查（仅做存在性检测）
        if not has_spec:
            return out

        # 配对 tool_result 找 review 输出
        results_by_id = self._collect_tool_results(entries)

        for call_entry, tool_use_id, sub_type, idx in review_calls:
            result_text = results_by_id.get(tool_use_id, "")
            expected_for_event = list(expected_types) if expected_types else [sub_type]

            # 1) subagent_type 不匹配
            if expected_types and sub_type not in expected_types:
                out.append(ReviewContractEvent(
                    kind="review_contract",
                    issue="subagent_type_mismatch",
                    reviewer_subagent_type=sub_type,
                    expected_subagent_types=expected_for_event,
                    actual_subagent_type=sub_type,
                    retry_count=0,
                    evidence_ref=call_entry.uuid() or "",
                    at=call_entry.timestamp(),
                ))

            # 2) 缺少 passed/retryAdvice 字段（仅当 spec 显式声明 required_fields）
            parsed = self._safe_parse(result_text)
            missing = []
            if required_fields:
                if "passed" in required_fields and (not isinstance(parsed, dict) or "passed" not in parsed):
                    missing.append("passed")
                if "retryAdvice" in required_fields and (not isinstance(parsed, dict) or "retryAdvice" not in parsed):
                    missing.append("retryAdvice")
            if missing:
                out.append(ReviewContractEvent(
                    kind="review_contract",
                    issue="missing_required_field",
                    reviewer_subagent_type=sub_type,
                    expected_subagent_types=expected_for_event,
                    actual_subagent_type=sub_type,
                    retry_count=max_retries,
                    evidence_ref=call_entry.uuid() or "",
                    at=call_entry.timestamp(),
                ))

            # 3) retry_count 超出（仅当 spec 声明 retry_count）
            if max_retries:
                retry_count = parsed.get("retryCount", 0) if isinstance(parsed, dict) else 0
                if isinstance(retry_count, int) and retry_count > max_retries:
                    out.append(ReviewContractEvent(
                        kind="review_contract",
                        issue="retry_exceeded",
                        reviewer_subagent_type=sub_type,
                        expected_subagent_types=expected_for_event,
                        actual_subagent_type=sub_type,
                        retry_count=retry_count,
                        evidence_ref=call_entry.uuid() or "",
                        at=call_entry.timestamp(),
                    ))

        return [e.to_dict() for e in out]

    @staticmethod
    def _collect_tool_results(entries: List[ClassifiedEntry]) -> Dict[str, str]:
        """tool_use_id → tool_result 文本（toolUseResult 字段或 message.content[*].content）。"""
        results: Dict[str, str] = {}
        for e in entries:
            if e.entry_class != "tool_result":
                continue
            content = (e.raw.get("message", {}) or {}).get("content", []) or []
            tur = e.raw.get("toolUseResult")
            for item in content:
                if not isinstance(item, dict):
                    continue
                tuid = item.get("tool_use_id", "")
                if not tuid:
                    continue
                # 优先 toolUseResult（结构化）
                text = ""
                if isinstance(tur, dict):
                    text = json.dumps(tur, ensure_ascii=False)
                elif isinstance(tur, str):
                    text = tur
                if not text and isinstance(item.get("content"), str):
                    text = item["content"]
                results[tuid] = text
        return results

    @staticmethod
    def _safe_parse(text: str) -> Any:
        if not text:
            return None
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return None