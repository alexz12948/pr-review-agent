"""
Tests for the automated-fix flow: findings persistence, fix endpoints,
the fix orchestrator, and the extended stats endpoint.

Devin and GitHub HTTP calls are mocked with respx.

To run:
    pip install pytest pytest-asyncio respx httpx
    pytest tests/test_fixes.py
"""

import json

import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.config import settings
from app.database import async_session, init_db
from app.main import app
from app.models import Finding, FixAction, ReviewRecord


@pytest.fixture(autouse=True)
def _override_settings(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "test-secret-123")
    monkeypatch.setattr(settings, "DEVIN_API_KEY", "fake-devin-key")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "fake-github-token")


@pytest_asyncio.fixture(autouse=True)
async def _clean_db():
    """Recreate the schema fresh for each test."""
    import os

    os.makedirs("data", exist_ok=True)
    from app.database import engine
    from sqlmodel import SQLModel

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await init_db()


async def _seed_review_with_findings() -> tuple[int, list[int]]:
    """Insert a review and two findings (one security, one quality)."""
    async with async_session() as db:
        review = ReviewRecord(
            repo="owner/repo",
            pr_number=42,
            head_sha="abc123",
            status="success",
            has_pending_fixes=True,
        )
        db.add(review)
        await db.flush()
        sec = Finding(
            review_id=review.id,
            agent_type="security",
            severity="critical",
            title="SQL injection",
            description="Unsanitized input",
            file="app/db.py",
            line=10,
            raw_json=json.dumps({"title": "SQL injection"}),
        )
        qual = Finding(
            review_id=review.id,
            agent_type="quality",
            category="bug",
            title="Off-by-one",
            description="Loop bound is wrong",
            file="app/util.py",
            line=20,
            raw_json=json.dumps({"title": "Off-by-one"}),
        )
        db.add(sec)
        db.add(qual)
        await db.commit()
        await db.refresh(review)
        await db.refresh(sec)
        await db.refresh(qual)
        return review.id, [sec.id, qual.id]


def _mock_apis(fix_status: str = "fixed", commit_sha: str = "deadbeef1234"):
    """Register respx mocks for Devin + GitHub APIs."""
    respx.post("https://api.devin.ai/v1/sessions").mock(
        return_value=Response(200, json={"session_id": "fix-sess"})
    )
    respx.get("https://api.devin.ai/v1/sessions/fix-sess").mock(
        return_value=Response(
            200,
            json={
                "status_enum": "finished",
                "structured_output": json.dumps(
                    {
                        "status": fix_status,
                        "commit_sha": commit_sha,
                        "summary": "Did the fix",
                    }
                ),
            },
        )
    )
    # get_pr_diff and get_pr_metadata both hit the pulls endpoint.
    respx.get("https://api.github.com/repos/owner/repo/pulls/42").mock(
        return_value=Response(
            200,
            json={
                "title": "Test PR",
                "head": {"ref": "feature-branch", "sha": "abc123"},
                "html_url": "https://github.com/owner/repo/pull/42",
            },
        )
    )
    respx.post(
        "https://api.github.com/repos/owner/repo/issues/42/comments"
    ).mock(return_value=Response(201, json={"id": 1}))


@pytest.mark.asyncio
async def test_get_findings_endpoint():
    review_id, finding_ids = await _seed_review_with_findings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/reviews/{review_id}/findings")
    assert resp.status_code == 200
    findings = resp.json()
    assert len(findings) == 2
    assert {f["fix_status"] for f in findings} == {"pending"}


@pytest.mark.asyncio
async def test_post_fix_single_validation():
    review_id, _ = await _seed_review_with_findings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing finding_id for single scope -> 400
        resp = await client.post(
            f"/api/reviews/{review_id}/fix", json={"scope": "single"}
        )
        assert resp.status_code == 400
        # Unknown review -> 404
        resp = await client.post(
            "/api/reviews/9999/fix", json={"scope": "all"}
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_run_fix_single_marks_finding_fixed():
    from app.services.fix_orchestrator import run_fix_single

    review_id, finding_ids = await _seed_review_with_findings()
    _mock_apis(fix_status="fixed")

    fix_action_id = await run_fix_single(review_id, finding_ids[0])

    async with async_session() as db:
        fa = await db.get(FixAction, fix_action_id)
        assert fa.status == "completed"
        assert fa.commit_sha == "deadbeef1234"
        assert fa.fix_pr_url.endswith("deadbeef1234")
        assert fa.latency_seconds is not None
        assert fa.completed_at is not None

        fixed = await db.get(Finding, finding_ids[0])
        other = await db.get(Finding, finding_ids[1])
        assert fixed.fix_status == "fixed"
        assert other.fix_status == "pending"

        review = await db.get(ReviewRecord, review_id)
        assert review.fix_actions_count == 1
        # One finding still pending.
        assert review.has_pending_fixes is True


@pytest.mark.asyncio
@respx.mock
async def test_run_fix_all_marks_all_fixed():
    from app.services.fix_orchestrator import run_fix_all

    review_id, finding_ids = await _seed_review_with_findings()
    _mock_apis(fix_status="fixed")

    fix_action_id = await run_fix_all(review_id)

    async with async_session() as db:
        fa = await db.get(FixAction, fix_action_id)
        assert fa.status == "completed"
        assert fa.scope == "all_review"
        assert set(json.loads(fa.finding_ids)) == set(finding_ids)

        for fid in finding_ids:
            f = await db.get(Finding, fid)
            assert f.fix_status == "fixed"

        review = await db.get(ReviewRecord, review_id)
        assert review.has_pending_fixes is False


@pytest.mark.asyncio
@respx.mock
async def test_run_fix_skipped_marks_failed():
    from app.services.fix_orchestrator import run_fix_single

    review_id, finding_ids = await _seed_review_with_findings()
    _mock_apis(fix_status="skipped", commit_sha="")

    fix_action_id = await run_fix_single(review_id, finding_ids[0])

    async with async_session() as db:
        fa = await db.get(FixAction, fix_action_id)
        assert fa.status == "failed"
        f = await db.get(Finding, finding_ids[0])
        assert f.fix_status == "failed"


@pytest.mark.asyncio
@respx.mock
async def test_stats_includes_fix_metrics():
    from app.services.fix_orchestrator import run_fix_single

    review_id, finding_ids = await _seed_review_with_findings()
    _mock_apis(fix_status="fixed")
    await run_fix_single(review_id, finding_ids[0])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert "fix_stats" in stats
    assert stats["fix_stats"]["total_fix_actions"] == 1
    assert stats["fix_stats"]["successful_fixes"] == 1
    assert stats["fix_stats"]["fix_success_rate"] == 1.0


@pytest.mark.asyncio
async def test_init_db_adds_missing_columns_to_existing_table():
    """init_db() should ALTER an existing review_records table that predates the
    fix-workflow columns, instead of leaving them missing (create_all does not
    ALTER existing tables)."""
    from sqlmodel import SQLModel

    from app.database import engine

    # Simulate a pre-existing DB: drop the new columns from review_records.
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.exec_driver_sql(
            "CREATE TABLE review_records ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, repo VARCHAR, pr_number INTEGER, "
            "head_sha VARCHAR, status VARCHAR, created_at DATETIME)"
        )
        await conn.exec_driver_sql(
            "INSERT INTO review_records (repo, pr_number, head_sha, status) "
            "VALUES ('owner/repo', 1, 'sha', 'success')"
        )

    # Run twice to confirm the migration is idempotent.
    await init_db()
    await init_db()

    async with engine.begin() as conn:
        rows = await conn.exec_driver_sql("PRAGMA table_info(review_records)")
        cols = {r[1] for r in rows.fetchall()}
    assert "fix_actions_count" in cols
    assert "has_pending_fixes" in cols

    # The new columns are now writable, and the pre-existing row got defaults.
    async with async_session() as db:
        review = await db.get(ReviewRecord, 1)
        assert review.fix_actions_count == 0
        assert review.has_pending_fixes in (False, 0)
        review.fix_actions_count = 3
        review.has_pending_fixes = True
        db.add(review)
        await db.commit()

    async with async_session() as db:
        review = await db.get(ReviewRecord, 1)
        assert review.fix_actions_count == 3
