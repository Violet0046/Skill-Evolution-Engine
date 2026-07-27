"""
backend/app/schemas/change.py — change 相关的 API 出入参模型

DDL 见 ../infra/core/review_db/ddl/004_see_evolution_change.sql (SEE 项目).
注: 见 evolution_change 表没有 status 字段 (用户决策 2026-07-25,
评审事件追踪放 see_review_decision). 因此 ChangeListItem 没有 status, 取
3 个 decision_count_* 字段 (后端聚合好的评审计数).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChangeListItem(BaseModel):
    """列表页用, 字段裁剪过大内容 (original/new 截到长度, suggestions 截到数组长度)."""
    id: int
    run_id: str
    subject_target: str
    original_length: int = Field(default=0, description="original_content 字节数")
    new_length: int = Field(default=0, description="new_content 字节数")
    suggestions_count: int = Field(default=0, description="suggestions_json 数组长度")

    # 评审事件聚合 (来自 see_review_decision LEFT JOIN + GROUP BY)
    decision_count_approved: int = Field(default=0)
    decision_count_modified: int = Field(default=0)
    decision_count_rejected: int = Field(default=0)

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "run_id": "2026-07-25-141911",
                "subject_target": "需求分析Agent@skills/查询需求信息/SKILL.md",
                "original_length": 4521,
                "new_length": 4789,
                "suggestions_count": 3,
                "decision_count_approved": 2,
                "decision_count_modified": 0,
                "decision_count_rejected": 0,
            }
        }


class ChangeOut(BaseModel):
    """详情页用, 含完整 original_content + new_content + suggestions_json.

    created_at / updated_at 暂留 None — 表里没这两列, 未来加列升级时启用.
    """
    id: int
    run_id: str
    subject_target: str
    original_content: str = ""
    new_content: str = ""
    suggestions_json: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="推动这个 change 的 suggestions 数组 (来自 see_evolution_change.suggestions_json)",
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 后端预计算的 diff, 来自 see_evolution_change.linediff_json.
    # 形态: { leftLines, rightLines, added, removed }
    linediff: Optional[Dict[str, Any]] = None
