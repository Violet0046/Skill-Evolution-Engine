"""
backend/app/api/decisions.py — 评审人提交决策

POST /api/changes/{change_id}/decisions
  body: DecisionIn  (decision / comment / modified_content? / reviewer?)

返回: 写入后那一行的 id + reviewed_at (来自 DB 端 NOW(3)).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.queries import insert_decision
from app.db.session import get_db
from app.schemas.decision import DecisionIn, DecisionOut

router = APIRouter(tags=["decisions"])


@router.post(
    "/api/changes/{change_id}/decisions",
    response_model=DecisionOut,
    summary="提交一次评审决策 (一个评审人对一条 change)",
)
def post_decision(
    change_id: int,
    body: DecisionIn,
    db: Session = Depends(get_db),
) -> DecisionOut:
    """
    MVP: 同一评审人对同一 change 可记多次 (event-sourced, 不去重).
    modified_content 仅当 decision == 'modified' 时必填.
    reviewed_at 用 DB 端 NOW(3) 计算, 由 queries.insert_decision 二次查拿回.
    """
    # 入参校验: modified 决策必须带 modified_content
    if body.decision.value == "modified" and not body.modified_content:
        raise HTTPException(
            status_code=422,
            detail="decision='modified' 时 modified_content 必填",
        )

    row = insert_decision(
        db,
        change_id=change_id,
        decision=body.decision.value,
        reviewer=body.reviewer,
        comment=body.comment,
        modified_content=body.modified_content,
    )
    return DecisionOut(
        id=row.get("id", 0),
        evolution_change_id=change_id,
        decision=row.get("decision", body.decision.value),
        reviewer=row.get("reviewer", body.reviewer),
        reviewed_at=row.get("reviewed_at"),  # 已 ISO 化, 来源 DB
    )
