"""
backend/app/schemas/evidence.py — see_evidence 的 API 出参

DDL 见 ../infra/core/review_db/ddl/003_see_evidence.sql.
"""
from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class EvidenceOut(BaseModel):
    """单条 evidence 详情. detail_json 是 see_entry_detail 返回的 5 字段 dict."""
    session_id: str
    uuid: str
    detail_json: Dict[str, Any] = Field(
        default_factory=dict,
        description="原始 detail 工具返回的 5 字段: reasoning_before / tool_name / input_params / error_output / reasoning_after",
    )
