import hashlib
import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.database import get_db
from app.models import ReviewRecord
from app.services.orchestrator import run_orchestrator

router = APIRouter()


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify the X-Hub-Signature-256 header using HMAC-SHA256."""
    # Refuse to verify when no secret is configured: an empty key would allow
    # an attacker to forge a valid signature and bypass verification.
    if not secret:
        return False
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/webhook/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(...),
    x_github_event: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()

    # Verify webhook signature
    if not verify_signature(payload, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Only process pull_request events
    if x_github_event != "pull_request":
        return JSONResponse(status_code=200, content={"detail": "Event ignored"})

    body = await request.json()
    action = body.get("action")

    # Only process opened or synchronize actions
    if action not in ("opened", "synchronize"):
        return JSONResponse(status_code=200, content={"detail": "Action ignored"})

    pr = body.get("pull_request", {})
    repo = body.get("repository", {}).get("full_name", "")
    pr_number = pr.get("number")
    head_sha = pr.get("head", {}).get("sha", "")

    # Idempotency check
    stmt = select(ReviewRecord).where(
        ReviewRecord.repo == repo,
        ReviewRecord.pr_number == pr_number,
        ReviewRecord.head_sha == head_sha,
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    if existing:
        return JSONResponse(status_code=200, content={"detail": "Review already exists for this SHA"})

    # Insert a placeholder record to prevent TOCTOU race with GitHub retries
    placeholder = ReviewRecord(
        repo=repo,
        pr_number=pr_number,
        head_sha=head_sha,
        status="pending",
    )
    db.add(placeholder)
    await db.commit()

    # Dispatch orchestrator as a background task
    background_tasks.add_task(run_orchestrator, body)

    return {"detail": "Review dispatched"}
