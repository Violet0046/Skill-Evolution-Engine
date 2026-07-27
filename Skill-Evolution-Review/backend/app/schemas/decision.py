"""
backend/app/schemas/decision.py — 评审动作入参

DDL 见 ../infra/core/review_db/ddl/005_see_review_decision.sql.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DecisionEnum(str, Enum):
    """评审动作枚举. 对齐 DDL 005 的 ENUM."""
    approved = "approved"
    modified = "modified"
    rejected = "rejected"


class DecisionIn(BaseModel):
    """POST 入参. review_id 暂留 optional, MVP 阶段前端用一个默认即可."""
    decision: DecisionEnum
    comment: Optional[str] = Field(default=None, description="评审人说明")
    modified_content: Optional[str] = Field(
        default=None,
        description="decision='modified' 时必填, 其余 decision 可为空",
    )
    reviewer: str = Field(
        default="anonymous",
        description="MVP 阶段暂记 'anonymous', 后续接入 auth 后从登录态取",
    )


class DecisionOut(BaseModel):
    """POST 返回: 写入后那一行的关键字段."""
    id: int
    evolution_change_id: int
    decision: str
    reviewer: str
    reviewed_at: str
