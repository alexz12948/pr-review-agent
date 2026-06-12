---
name: testing-dashboard
description: Test the PR Review Agent dashboard end-to-end. Use when verifying dashboard UI, findings display, or API changes.
---

# Testing the PR Review Agent Dashboard

## Prerequisites

- Python 3.12+ with dependencies from `requirements.txt`
- Node.js 18+ for frontend build

## Devin Secrets Needed

- `GITHUB_WEBHOOK_SECRET` — can use any dummy value (e.g. `test-secret-123`) for local testing since no real webhook calls are made

## Setup Steps

### 1. Build the Frontend

```bash
cd frontend
npm install
npm run build
```

This produces `frontend/dist/` which the FastAPI server serves at `/dashboard`.

### 2. Start the FastAPI Server

```bash
GITHUB_WEBHOOK_SECRET=test-secret-123 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The dashboard is at `http://localhost:8000/dashboard`.

### 3. Seed Test Data

Write a Python script that uses `app.database.init_db` and `app.database.async_session` to insert `ReviewRecord` and `Finding` rows directly. Key fields:

- **ReviewRecord**: `repo`, `pr_number`, `head_sha`, `security_findings`, `quality_findings`, `critical_count`, `high_count`, `medium_count`, `low_count`, `latency_seconds`, `status`
- **Finding**: `review_id`, `agent_type` ("security" or "quality"), `severity` (for security), `category` (for quality), `title`, `description`, `file`, `line`, `raw_json`

Make sure `created_at` is populated (SQLModel default should handle it, but if inserting raw SQL, set it explicitly) — the `/api/reviews` endpoint calls `.isoformat()` on it and will 500 if it's `None`.

## What to Test

### API Endpoints

- `GET /api/stats` — returns `total_security_findings`, `total_quality_findings`, severity breakdown
- `GET /api/reviews` — returns list of reviews with finding counts
- `GET /api/reviews/{id}/findings` — returns individual findings for a review

### Dashboard UI

1. **StatCards**: "Total Findings" should equal `total_security_findings + total_quality_findings` (not just severity sum)
2. **Reviews Table**: Each row shows Security and Quality counts — verify they're non-zero when findings exist
3. **Detail Modal**: Click a review row to open the modal. Verify:
   - Individual findings are listed (not "No findings recorded")
   - Security findings show severity badges (critical/high/medium/low)
   - Quality findings show category badges (bug/testing/performance/etc.)
   - Each finding shows title, description, file:line, fix status
4. **Severity Pie Chart**: Should show colored segments matching severity counts

## Known Gotchas

- The DB is SQLite at `./data/pr_reviews.db`. If you see stale data or 500 errors, delete it and re-seed.
- Old/corrupted records with `created_at=None` will cause `/api/reviews` to return 500. Clean the DB if this happens.
- The `structured_output` from the Devin API may be a `dict` or a JSON `str` — the parsers in `orchestrator.py` handle both. When writing tests, test both input types.
- Quality findings use `category` (bug, consistency, testing, performance) not `severity`. They won't appear in severity-based counts but should appear in `total_quality_findings`.
