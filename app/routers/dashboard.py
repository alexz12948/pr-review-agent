import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import FRONTEND_INDEX
from app.database import get_db
from app.models import FixAction, ReviewRecord

router = APIRouter()


@router.get("/api/reviews")
async def get_reviews(db: AsyncSession = Depends(get_db)):
    """Return JSON list of recent ReviewRecords (limit 100, ordered by created_at desc)."""
    stmt = select(ReviewRecord).order_by(ReviewRecord.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "repo": r.repo,
            "pr_number": r.pr_number,
            "head_sha": r.head_sha,
            "security_findings": r.security_findings,
            "quality_findings": r.quality_findings,
            "critical_count": r.critical_count,
            "high_count": r.high_count,
            "medium_count": r.medium_count,
            "low_count": r.low_count,
            "latency_seconds": r.latency_seconds,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@router.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Return aggregate stats: total PRs, findings by severity, avg latency."""
    total_stmt = select(func.count(ReviewRecord.id))
    total_result = await db.execute(total_stmt)
    total_prs = total_result.scalar() or 0

    avg_latency_stmt = select(func.avg(ReviewRecord.latency_seconds))
    avg_latency_result = await db.execute(avg_latency_stmt)
    avg_latency = avg_latency_result.scalar() or 0.0

    severity_stmt = select(
        func.sum(ReviewRecord.critical_count),
        func.sum(ReviewRecord.high_count),
        func.sum(ReviewRecord.medium_count),
        func.sum(ReviewRecord.low_count),
        func.sum(ReviewRecord.security_findings),
        func.sum(ReviewRecord.quality_findings),
    )
    severity_result = await db.execute(severity_stmt)
    row = severity_result.one()

    # Fix-related aggregates
    total_fix_stmt = select(func.count(FixAction.id))
    total_fix_actions = (await db.execute(total_fix_stmt)).scalar() or 0

    successful_fix_stmt = select(func.count(FixAction.id)).where(
        FixAction.status == "completed"
    )
    successful_fixes = (await db.execute(successful_fix_stmt)).scalar() or 0

    failed_fix_stmt = select(func.count(FixAction.id)).where(
        FixAction.status == "failed"
    )
    failed_fixes = (await db.execute(failed_fix_stmt)).scalar() or 0

    avg_fix_latency_stmt = select(func.avg(FixAction.latency_seconds)).where(
        FixAction.latency_seconds.is_not(None)
    )
    avg_fix_latency = (await db.execute(avg_fix_latency_stmt)).scalar() or 0.0

    fix_success_rate = (
        round(successful_fixes / total_fix_actions, 4)
        if total_fix_actions
        else 0.0
    )

    return {
        "total_prs": total_prs,
        "avg_latency": round(avg_latency, 2),
        "total_findings": {
            "critical": row[0] or 0,
            "high": row[1] or 0,
            "medium": row[2] or 0,
            "low": row[3] or 0,
        },
        "total_security_findings": row[4] or 0,
        "total_quality_findings": row[5] or 0,
        "fix_stats": {
            "total_fix_actions": total_fix_actions,
            "successful_fixes": successful_fixes,
            "failed_fixes": failed_fixes,
            "fix_success_rate": fix_success_rate,
            "avg_fix_latency": round(avg_fix_latency, 2),
        },
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    if os.path.exists(FRONTEND_INDEX):
        return FileResponse(FRONTEND_INDEX)
    return HTMLResponse("<h1>Dashboard not built</h1>", status_code=503)
