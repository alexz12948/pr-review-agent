import json
import logging
import time
from datetime import datetime, timezone

from sqlmodel import select

from app.database import async_session
from app.models import Finding, FixAction, ReviewRecord
from app.services.devin_client import create_session, poll_session
from app.services.github_client import (
    get_pr_diff,
    get_pr_metadata,
    post_review_comment,
)
from app.services.orchestrator import _extract_output
from app.services.prompts import fix_batch_prompt, fix_single_prompt

logger = logging.getLogger(__name__)


def _finding_to_dict(finding: Finding) -> dict:
    """Serialize a Finding ORM row into a plain dict for prompt building."""
    return {
        "id": finding.id,
        "agent_type": finding.agent_type,
        "severity": finding.severity,
        "category": finding.category,
        "title": finding.title,
        "description": finding.description,
        "file": finding.file,
        "line": finding.line,
    }


def _parse_fix_result(output: str) -> dict:
    """Parse the JSON result emitted by a fix agent."""
    result = {"status": None, "commit_sha": None, "summary": None}
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            result["status"] = data.get("status")
            result["commit_sha"] = data.get("commit_sha")
            result["summary"] = data.get("summary")
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse fix result JSON; storing raw output")
        result["summary"] = output[:2000] if output else None
    return result


async def create_fix_action(
    db, review_id: int, finding_ids: list[int], scope: str
) -> FixAction:
    """Create a queued FixAction and mark the targeted findings as in_progress.

    Runs synchronously so callers (e.g. the API endpoint) can return the new
    FixAction id before the heavy lifting is dispatched to a background task.
    """
    fix_action = FixAction(
        review_id=review_id,
        finding_ids=json.dumps(finding_ids),
        scope=scope,
        status="queued",
    )
    db.add(fix_action)

    if finding_ids:
        stmt = select(Finding).where(Finding.id.in_(finding_ids))
        result = await db.execute(stmt)
        for finding in result.scalars().all():
            finding.fix_status = "in_progress"
            db.add(finding)

    review = await db.get(ReviewRecord, review_id)
    if review:
        review.fix_actions_count = (review.fix_actions_count or 0) + 1
        db.add(review)

    await db.commit()
    await db.refresh(fix_action)
    return fix_action


async def execute_fix(fix_action_id: int) -> None:
    """Background worker that runs a Devin fix session for a FixAction."""
    start_time = time.time()
    session_id = None

    # Load the fix action, its findings, and the parent review.
    async with async_session() as db:
        fix_action = await db.get(FixAction, fix_action_id)
        if fix_action is None:
            logger.error("FixAction %d not found", fix_action_id)
            return

        review = await db.get(ReviewRecord, fix_action.review_id)
        if review is None:
            logger.error("ReviewRecord %d not found", fix_action.review_id)
            return

        finding_ids = json.loads(fix_action.finding_ids or "[]")
        findings: list[Finding] = []
        if finding_ids:
            stmt = select(Finding).where(Finding.id.in_(finding_ids))
            result = await db.execute(stmt)
            findings = list(result.scalars().all())

        fix_action.status = "in_progress"
        db.add(fix_action)
        await db.commit()

        repo = review.repo
        pr_number = review.pr_number
        finding_dicts = [_finding_to_dict(f) for f in findings]
        scope = fix_action.scope

    try:
        # Gather context for the fix session.
        diff = await get_pr_diff(repo, pr_number)
        try:
            pr_metadata = await get_pr_metadata(repo, pr_number)
        except Exception:
            logger.warning("Could not fetch PR metadata; using minimal metadata")
            pr_metadata = {"repo": repo, "pr_number": pr_number}

        if scope == "single" and len(finding_dicts) == 1:
            prompt = fix_single_prompt(finding_dicts[0], diff, pr_metadata)
        else:
            prompt = fix_batch_prompt(finding_dicts, diff, pr_metadata)

        session_id = await create_session(prompt)

        async with async_session() as db:
            fix_action = await db.get(FixAction, fix_action_id)
            if fix_action:
                fix_action.devin_session_id = session_id
                db.add(fix_action)
                await db.commit()

        session_result = await poll_session(session_id)
        output = _extract_output(session_result)
        parsed = _parse_fix_result(output)

        fixed = parsed.get("status") == "fixed"
        commit_sha = parsed.get("commit_sha") or None
        summary = parsed.get("summary")
        latency = time.time() - start_time

        fix_pr_url = None
        if commit_sha:
            fix_pr_url = f"https://github.com/{repo}/commit/{commit_sha}"

        await _finalize(
            fix_action_id=fix_action_id,
            finding_ids=finding_ids,
            status="completed" if fixed else "failed",
            finding_status="fixed" if fixed else "failed",
            commit_sha=commit_sha,
            fix_pr_url=fix_pr_url,
            result_summary=summary,
            latency=latency,
        )

        # Notify the PR with a comment summarizing the auto-fix attempt.
        try:
            await post_review_comment(
                repo,
                pr_number,
                _build_fix_comment(
                    fixed=fixed,
                    summary=summary,
                    commit_sha=commit_sha,
                    fix_pr_url=fix_pr_url,
                    num_findings=len(finding_dicts),
                    session_id=session_id,
                ),
            )
        except Exception:
            logger.exception("Failed to post auto-fix comment on PR")

        logger.info(
            "Fix action %d completed (fixed=%s, %.1fs)",
            fix_action_id,
            fixed,
            latency,
        )

    except Exception:
        latency = time.time() - start_time
        logger.exception("Fix action %d failed", fix_action_id)
        await _finalize(
            fix_action_id=fix_action_id,
            finding_ids=finding_ids,
            status="failed",
            finding_status="failed",
            commit_sha=None,
            fix_pr_url=None,
            result_summary="Fix session failed; see logs for details.",
            latency=latency,
        )


async def _finalize(
    fix_action_id: int,
    finding_ids: list[int],
    status: str,
    finding_status: str,
    commit_sha: str | None,
    fix_pr_url: str | None,
    result_summary: str | None,
    latency: float,
) -> None:
    """Persist the terminal state of a fix action and its findings."""
    async with async_session() as db:
        fix_action = await db.get(FixAction, fix_action_id)
        if fix_action is not None:
            fix_action.status = status
            fix_action.commit_sha = commit_sha
            fix_action.fix_pr_url = fix_pr_url
            fix_action.result_summary = result_summary
            fix_action.latency_seconds = latency
            fix_action.completed_at = datetime.now(timezone.utc)
            db.add(fix_action)

            review = await db.get(ReviewRecord, fix_action.review_id)
        else:
            review = None

        if finding_ids:
            stmt = select(Finding).where(Finding.id.in_(finding_ids))
            result = await db.execute(stmt)
            for finding in result.scalars().all():
                finding.fix_status = finding_status
                db.add(finding)

        # Recompute whether the review still has fixable pending findings.
        if review is not None:
            pending_stmt = select(Finding).where(
                Finding.review_id == review.id,
                Finding.fix_status == "pending",
            )
            pending_result = await db.execute(pending_stmt)
            review.has_pending_fixes = pending_result.scalars().first() is not None
            db.add(review)

        await db.commit()


def _build_fix_comment(
    fixed: bool,
    summary: str | None,
    commit_sha: str | None,
    fix_pr_url: str | None,
    num_findings: int,
    session_id: str | None,
) -> str:
    """Build a markdown comment summarizing an auto-fix attempt."""
    header = (
        "## 🤖 Automated Fix Applied"
        if fixed
        else "## 🤖 Automated Fix Attempt"
    )
    status_line = (
        f"Addressed **{num_findings}** finding(s)."
        if fixed
        else f"Attempted to address **{num_findings}** finding(s), but no fix was committed."
    )
    parts = [header, "", status_line, ""]
    if summary:
        parts.append(f"**Summary:** {summary}")
        parts.append("")
    if commit_sha and fix_pr_url:
        parts.append(f"**Commit:** [`{commit_sha[:8]}`]({fix_pr_url})")
        parts.append("")
    if session_id:
        parts.append(
            f"_Fixed by Devin session [`{session_id}`]"
            f"(https://app.devin.ai/sessions/{session_id})._"
        )
    return "\n".join(parts)


async def _run_fix_for_findings(
    review_id: int, finding_ids: list[int], scope: str
) -> int:
    """Create a fix action for the given findings and execute it.

    Returns the created FixAction id. Used by the convenience entrypoints below
    when they are invoked directly (rather than via the API, which creates the
    FixAction synchronously and dispatches ``execute_fix``).
    """
    async with async_session() as db:
        fix_action = await create_fix_action(db, review_id, finding_ids, scope)
        fix_action_id = fix_action.id
    await execute_fix(fix_action_id)
    return fix_action_id


async def _pending_finding_ids(
    db,
    review_id: int,
    agent_type: str | None = None,
    severity: str | None = None,
) -> list[int]:
    """Return ids of pending findings for a review, optionally filtered."""
    stmt = select(Finding).where(
        Finding.review_id == review_id,
        Finding.fix_status == "pending",
    )
    if agent_type:
        stmt = stmt.where(Finding.agent_type == agent_type)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    result = await db.execute(stmt)
    return [f.id for f in result.scalars().all()]


async def run_fix_single(review_id: int, finding_id: int) -> int:
    """Fix a single finding."""
    return await _run_fix_for_findings(review_id, [finding_id], "single")


async def run_fix_all(review_id: int) -> int:
    """Fix all pending findings for a review."""
    async with async_session() as db:
        finding_ids = await _pending_finding_ids(db, review_id)
    return await _run_fix_for_findings(review_id, finding_ids, "all_review")


async def run_fix_by_filter(
    review_id: int,
    agent_type: str | None = None,
    severity: str | None = None,
) -> int:
    """Fix pending findings filtered by agent_type and/or severity."""
    async with async_session() as db:
        finding_ids = await _pending_finding_ids(
            db, review_id, agent_type=agent_type, severity=severity
        )
    scope = "by_agent" if agent_type else "by_severity"
    return await _run_fix_for_findings(review_id, finding_ids, scope)
