"""
backend/app/api/changes.py — change 列表 + 详情

TODO (开干 2 接 SQL):
  - list_changes_for_run: 真的查 DB
  - get_change_by_id: 真的查 DB
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.queries import (
    get_change_by_id,
    list_changes_for_run,
    list_runs,
)
from app.db.session import get_db
from app.schemas.change import ChangeListItem, ChangeOut

router = APIRouter(tags=["changes"])


@router.get(
    "/api/runs",
    response_model=List[str],
    summary="列出所有出现过的 run_id (倒序)",
)
def list_runs_endpoint(
    db: Session = Depends(get_db),
) -> List[str]:
    """用于前端评审员挑选想要评审的 run.
    返回 ['2026-07-25-141911', '2026-07-20-161903', ...]."""
    return list_runs(db)


@router.get(
    "/api/runs/{run_id}/changes",
    response_model=List[ChangeListItem],
    summary="按 run_id 列出 changes",
)
def list_changes(
    run_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[ChangeListItem]:
    """按 run_id 列 see_evolution_change 的轻量字段.

    开干 1 stub: 返回 [], 让 Swagger 可见. 开干 2 接 list_changes_for_run.
    """
    rows = list_changes_for_run(db, run_id, limit=limit, offset=offset)
    return [ChangeListItem(**r) for r in rows]


@router.get(
    "/api/changes/{change_id}",
    response_model=ChangeOut,
    summary="单个 change 详情 (含 original + new + suggestions)",
)
def get_change(
    change_id: int,
    db: Session = Depends(get_db),
) -> ChangeOut:
    """返回 see_evolution_change 单行的完整内容.

    开干 1 stub: 找不到时让 FastAPI 抛 404. 开干 2 接 get_change_by_id.
    """
    row = get_change_by_id(db, change_id)
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"change {change_id} not found")
    return ChangeOut(**row)
