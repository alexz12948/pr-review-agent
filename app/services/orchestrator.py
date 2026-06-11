import asyncio
import json
import logging
import re
import time

from sqlmodel import select

from app.database import async_session
from app.models import Finding, ReviewRecord
from app.services.devin_client import create_session, poll_session
from app.services.github_client import get_pr_diff, post_review_comment
from app.services.prompts import quality_prompt, security_prompt, synthesis_prompt

logger = logging.getLogger(__name__)

# Regex to match a markdown-fenced code block (```json ... ``` or ``` ... ```)
_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL
)


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from *text* and return the inner content.

    LLM responses frequently wrap JSON in ```json ... ``` blocks despite
    being told not to.  If the text contains a fenced block, return its
    content; otherwise return the original text stripped of leading/trailing
    whitespace.
    """
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _extract_output(session_result: dict):
    """Extract structured output or last message from a session result.

    Returns a *str* (JSON) or *dict* depending on the API version.
    Downstream parsers accept both.
    """
    so = session_result.get("structured_output")
    if so is not None:
        return so
    # Fall back to the last message in the conversation
    messages = session_result.get("messages", [])
    if messages:
        return messages[-1].get("content", "")
    return ""


def _parse_json(output) -> dict | None:
    """Best-effort parse of *output* into a dict.

    Handles:
    * ``dict`` returned directly by the API's ``structured_output``
    * clean JSON strings
    * JSON wrapped in markdown code fences (``````json … ``````)

    Returns ``None`` when parsing fails.
    """
    if isinstance(output, dict):
        return output
    if not isinstance(output, str):
        return None
    # First try the raw string
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    # Strip markdown fences and retry
    cleaned = _strip_fences(output)
    if cleaned != output:
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _parse_finding_counts(output) -> dict:
    """Parse finding counts from JSON output.

    ``output`` may be a *str* (JSON text, possibly markdown-fenced) or a
    *dict* already parsed by the API client — both are handled transparently.
    """
    severity_keys = {"critical", "high", "medium", "low"}
    counts: dict = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    data = _parse_json(output)
    if data is None:
        logger.warning("Could not parse findings JSON")
        return counts
    findings = data.get("findings", [])
    counts["total"] = len(findings)
    for f in findings:
        severity = (f.get("severity") or "").lower()
        if severity in severity_keys:
            counts[severity] += 1
    return counts


def _parse_findings(output) -> list[dict]:
    """Parse the raw list of findings from an agent's JSON output.

    ``output`` may be a *str* (JSON text, possibly markdown-fenced) or a
    *dict*.
    """
    data = _parse_json(output)
    if data is None:
        logger.warning("Could not parse findings JSON")
        return []
    findings = data.get("findings", [])
    if isinstance(findings, list):
        return [f for f in findings if isinstance(f, dict)]
    return []


def _build_finding_rows(
    review_id: int, agent_type: str, findings: list[dict]
) -> list[Finding]:
    """Convert raw finding dicts into Finding ORM rows for one agent."""
    rows: list[Finding] = []
    for f in findings:
        severity = f.get("severity")
        category = f.get("category")
        rows.append(
            Finding(
                review_id=review_id,
                agent_type=agent_type,
                severity=severity.lower() if isinstance(severity, str) else None,
                category=category.lower() if isinstance(category, str) else None,
                title=str(f.get("title", "") or "")[:500] or "(untitled finding)",
                description=str(f.get("description", "") or ""),
                file=f.get("file") if isinstance(f.get("file"), str) else None,
                line=f.get("line") if isinstance(f.get("line"), int) else None,
                raw_json=json.dumps(f),
            )
        )
    return rows


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
        # synthesis_prompt uses f-string interpolation, so ensure string form
        sec_output_str = json.dumps(sec_output) if isinstance(sec_output, dict) else sec_output
        qual_output_str = json.dumps(qual_output) if isinstance(qual_output, dict) else qual_output
        synth_prompt = synthesis_prompt(sec_output_str, qual_output_str, pr_metadata)
        synthesis_sid = await create_session(synth_prompt)
        synth_result = await poll_session(synthesis_sid)

        # 6. Extract the final markdown
        final_comment = _extract_output(synth_result)
        # GitHub API expects a string body; guard against dict output
        if isinstance(final_comment, dict):
            final_comment = json.dumps(final_comment, indent=2)

        # 7. Post the review comment to GitHub
        await post_review_comment(repo, pr_number, final_comment)

        # 8. Parse finding counts and the individual findings
        sec_counts = _parse_finding_counts(sec_output)
        qual_counts = _parse_finding_counts(qual_output)
        sec_findings = _parse_findings(sec_output)
        qual_findings = _parse_findings(qual_output)

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
                record.critical_count = (
                    sec_counts["critical"] + qual_counts["critical"]
                )
                record.high_count = (
                    sec_counts["high"] + qual_counts["high"]
                )
                record.medium_count = (
                    sec_counts["medium"] + qual_counts["medium"]
                )
                record.low_count = (
                    sec_counts["low"] + qual_counts["low"]
                )
                record.latency_seconds = latency
                record.orchestrator_session_id = synthesis_sid
                record.security_session_id = security_sid
                record.quality_session_id = quality_sid
                record.status = "success"
                record.has_pending_fixes = bool(sec_findings or qual_findings)
                db.add(record)
                await db.flush()  # ensure record.id is populated

                finding_rows = _build_finding_rows(
                    record.id, "security", sec_findings
                ) + _build_finding_rows(record.id, "quality", qual_findings)
                for fr in finding_rows:
                    db.add(fr)
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
