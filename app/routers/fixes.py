import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_db
from app.models import Finding, FixAction, ReviewRecord
from app.services.fix_orchestrator import create_fix_action, execute_fix

router = APIRouter()

# Maps the API-facing scope to the internal FixAction.scope value.
_SCOPE_MAP = {
    "all": "all_review",
    "single": "single",
    "by_severity": "by_severity",
    "by_agent": "by_agent",
}


class FixRequest(BaseModel):
    scope: str  # "all" | "single" | "by_severity" | "by_agent"
    finding_id: Optional[int] = None  # required if scope == "single"
    severity: Optional[str] = None  # filter for scope == "by_severity"
    agent_type: Optional[str] = None  # filter for scope == "by_agent"


def _finding_to_dict(f: Finding) -> dict:
    return {
        "id": f.id,
        "review_id": f.review_id,
        "agent_type": f.agent_type,
        "severity": f.severity,
        "category": f.category,
        "title": f.title,
        "description": f.description,
        "file": f.file,
        "line": f.line,
        "fix_status": f.fix_status,
        "created_at": f.created_at.isoformat(),
    }


def _fix_action_to_dict(fa: FixAction) -> dict:
    return {
        "id": fa.id,
        "review_id": fa.review_id,
        "finding_ids": json.loads(fa.finding_ids or "[]"),
        "scope": fa.scope,
        "devin_session_id": fa.devin_session_id,
        "status": fa.status,
        "result_summary": fa.result_summary,
        "commit_sha": fa.commit_sha,
        "fix_pr_url": fa.fix_pr_url,
        "latency_seconds": fa.latency_seconds,
        "created_at": fa.created_at.isoformat(),
        "completed_at": fa.completed_at.isoformat() if fa.completed_at else None,
    }


@router.post("/api/reviews/{review_id}/fix", status_code=202)
async def trigger_fix(
    review_id: int,
    body: FixRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an automated fix for findings of a review.

    Returns 202 Accepted with the created FixAction id. The actual fix runs in a
    background task.
    """
    internal_scope = _SCOPE_MAP.get(body.scope)
    if internal_scope is None:
        raise HTTPException(status_code=400, detail=f"Invalid scope: {body.scope}")

    review = await db.get(ReviewRecord, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    # Build the set of pending findings to address based on the requested scope.
    if body.scope == "single":
        if body.finding_id is None:
            raise HTTPException(
                status_code=400,
                detail="finding_id is required when scope='single'",
            )
        finding = await db.get(Finding, body.finding_id)
        if finding is None or finding.review_id != review_id:
            raise HTTPException(
                status_code=404, detail="Finding not found for this review"
            )
        if finding.fix_status != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Finding is not pending (status={finding.fix_status})",
            )
        finding_ids = [finding.id]
    else:
        stmt = select(Finding).where(
            Finding.review_id == review_id,
            Finding.fix_status == "pending",
        )
        if body.scope == "by_severity":
            if not body.severity:
                raise HTTPException(
                    status_code=400,
                    detail="severity is required when scope='by_severity'",
                )
            stmt = stmt.where(Finding.severity == body.severity)
        elif body.scope == "by_agent":
            if not body.agent_type:
                raise HTTPException(
                    status_code=400,
                    detail="agent_type is required when scope='by_agent'",
                )
            stmt = stmt.where(Finding.agent_type == body.agent_type)
        result = await db.execute(stmt)
        finding_ids = [f.id for f in result.scalars().all()]

    if not finding_ids:
        raise HTTPException(
            status_code=404,
            detail="No pending findings match the requested scope",
        )

    fix_action = await create_fix_action(db, review_id, finding_ids, internal_scope)
    background_tasks.add_task(execute_fix, fix_action.id)

    return JSONResponse(
        status_code=202,
        content={
            "fix_action_id": fix_action.id,
            "status": fix_action.status,
            "finding_ids": finding_ids,
        },
    )


@router.get("/api/reviews/{review_id}/findings")
async def get_findings(review_id: int, db: AsyncSession = Depends(get_db)):
    """Return all findings for a review, including their fix_status."""
    review = await db.get(ReviewRecord, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    stmt = (
        select(Finding)
        .where(Finding.review_id == review_id)
        .order_by(Finding.id.asc())
    )
    result = await db.execute(stmt)
    return [_finding_to_dict(f) for f in result.scalars().all()]


@router.get("/api/fix-actions/{fix_action_id}")
async def get_fix_action(fix_action_id: int, db: AsyncSession = Depends(get_db)):
    """Return the current status of a single fix action (for UI polling)."""
    fix_action = await db.get(FixAction, fix_action_id)
    if fix_action is None:
        raise HTTPException(status_code=404, detail="Fix action not found")
    return _fix_action_to_dict(fix_action)


@router.get("/api/reviews/{review_id}/fix-actions")
async def get_fix_actions(review_id: int, db: AsyncSession = Depends(get_db)):
    """Return all fix actions for a review (newest first)."""
    review = await db.get(ReviewRecord, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    stmt = (
        select(FixAction)
        .where(FixAction.review_id == review_id)
        .order_by(FixAction.created_at.desc())
    )
    result = await db.execute(stmt)
    return [_fix_action_to_dict(fa) for fa in result.scalars().all()]
