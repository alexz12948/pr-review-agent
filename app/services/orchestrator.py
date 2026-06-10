import asyncio
import json
import logging
import time

from sqlmodel import select

from app.database import async_session
from app.models import ReviewRecord
from app.services.devin_client import create_session, poll_session
from app.services.github_client import get_pr_diff, post_review_comment
from app.services.prompts import quality_prompt, security_prompt, synthesis_prompt

logger = logging.getLogger(__name__)


def _extract_output(session_result: dict) -> str:
    """Extract structured output or last message from a session result."""
    # Prefer structured_output if available
    if session_result.get("structured_output"):
        return session_result["structured_output"]
    # Fall back to the last message in the conversation
    messages = session_result.get("messages", [])
    if messages:
        return messages[-1].get("content", "")
    return ""


def _parse_finding_counts(output: str) -> dict:
    """Parse finding counts from JSON output."""
    counts = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    try:
        data = json.loads(output)
        findings = data.get("findings", [])
        counts["total"] = len(findings)
        for f in findings:
            severity = f.get("severity", "").lower()
            if severity in counts:
                counts[severity] += 1
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.warning("Could not parse findings JSON")
    return counts


async def run_orchestrator(pr_payload: dict) -> None:
    """Main orchestrator: runs security + quality reviews, synthesizes, and posts."""
    start_time = time.time()

    repo = pr_payload.get("repository", {}).get("full_name", "")
    pr = pr_payload.get("pull_request", {})
    pr_number = pr.get("number")
    head_sha = pr.get("head", {}).get("sha", "")

    pr_metadata = {
        "repo": repo,
        "pr_number": pr_number,
        "title": pr.get("title", ""),
        "author": pr.get("user", {}).get("login", ""),
        "description": pr.get("body", ""),
        "head_sha": head_sha,
    }

    security_sid = ""
    quality_sid = ""
    synthesis_sid = ""

    try:
        # 1. Fetch the diff
        diff = await get_pr_diff(repo, pr_number)

        # 2. Launch security and quality sessions in parallel
        sec_prompt = security_prompt(diff, pr_metadata)
        qual_prompt = quality_prompt(diff, pr_metadata)

        security_sid, quality_sid = await asyncio.gather(
            create_session(sec_prompt),
            create_session(qual_prompt),
        )

        # 3. Poll both sessions in parallel
        sec_result, qual_result = await asyncio.gather(
            poll_session(security_sid),
            poll_session(quality_sid),
        )

        # 4. Extract structured output from each
        sec_output = _extract_output(sec_result)
        qual_output = _extract_output(qual_result)

        # 5. Create synthesis session and poll it
        synth_prompt = synthesis_prompt(sec_output, qual_output, pr_metadata)
        synthesis_sid = await create_session(synth_prompt)
        synth_result = await poll_session(synthesis_sid)

        # 6. Extract the final markdown
        final_comment = _extract_output(synth_result)

        # 7. Post the review comment to GitHub
        await post_review_comment(repo, pr_number, final_comment)

        # 8. Parse finding counts
        sec_counts = _parse_finding_counts(sec_output)
        qual_counts = _parse_finding_counts(qual_output)

        latency = time.time() - start_time

        # 9. Update the placeholder ReviewRecord in the database
        async with async_session() as db:
            stmt = select(ReviewRecord).where(
                ReviewRecord.repo == repo,
                ReviewRecord.pr_number == pr_number,
                ReviewRecord.head_sha == head_sha,
            )
            result = await db.execute(stmt)
            record = result.scalars().first()
            if record:
                record.security_findings = sec_counts["total"]
                record.quality_findings = qual_counts["total"]
                record.critical_count = sec_counts["critical"]
                record.high_count = sec_counts["high"]
                record.medium_count = sec_counts["medium"]
                record.low_count = sec_counts["low"]
                record.latency_seconds = latency
                record.orchestrator_session_id = synthesis_sid
                record.security_session_id = security_sid
                record.quality_session_id = quality_sid
                record.status = "success"
                db.add(record)
            await db.commit()

        logger.info(
            "Review completed for %s #%d (%.1fs)", repo, pr_number, latency
        )

    except Exception:
        latency = time.time() - start_time
        logger.exception("Orchestrator failed for %s #%d", repo, pr_number)

        # Update the placeholder record to failed status
        try:
            async with async_session() as db:
                stmt = select(ReviewRecord).where(
                    ReviewRecord.repo == repo,
                    ReviewRecord.pr_number == pr_number,
                    ReviewRecord.head_sha == head_sha,
                )
                result = await db.execute(stmt)
                record = result.scalars().first()
                if record:
                    record.latency_seconds = latency
                    record.orchestrator_session_id = synthesis_sid
                    record.security_session_id = security_sid
                    record.quality_session_id = quality_sid
                    record.status = "failed"
                    db.add(record)
                await db.commit()
        except Exception:
            logger.exception("Failed to save failure record")
