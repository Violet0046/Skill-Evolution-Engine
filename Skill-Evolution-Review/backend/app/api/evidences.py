"""
backend/app/api/evidences.py — evidence 下钻

设计: 见 see_review_decision 的 evidence_uuids[] 数组里任一项 evidence,
前端点开 → GET /api/evidences?session_id=X&uuid=Y → 5 字段详情.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.queries import get_evidence
from app.db.session import get_db
from app.schemas.evidence import EvidenceOut

router = APIRouter(tags=["evidences"])


@router.get(
    "/api/evidences",
    response_model=EvidenceOut,
    summary="按 (session_id, uuid) 取 evidence 详情",
)
def get_evidence_endpoint(
    session_id: str,
    uuid: str,
    db: Session = Depends(get_db),
) -> EvidenceOut:
    """UK = (session_id, uuid). 找不到 → 404."""
    row = get_evidence(db, session_id, uuid)
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"evidence ({session_id}, {uuid}) not found",
        )
    return EvidenceOut(**row)
