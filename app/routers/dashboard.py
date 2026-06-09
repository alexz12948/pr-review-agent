from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_db
from app.models import ReviewRecord

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the dashboard HTML template."""
    return templates.TemplateResponse("dashboard.html", {"request": request})
