---
name: testing-pr-review-dashboard
description: Test the PR Review Agent dashboard end-to-end. Use when verifying that findings from Devin review sessions appear correctly on the dashboard.
---

# Testing the PR Review Agent Dashboard

## Devin Secrets Needed
- `DEVIN_API_KEY` — for calling the Devin v1 API to fetch real session data
- `GITHUB_TOKEN` — for GitHub API operations
- `GITHUB_WEBHOOK_SECRET` — required for server startup (validated in lifespan)

## Server Setup

1. Build the frontend first:
   ```bash
   cd frontend && npm run build
   ```

2. Start the FastAPI server with env vars exported:
   ```bash
   export GITHUB_WEBHOOK_SECRET="${GITHUB_WEBHOOK_SECRET}"
   export DEVIN_API_KEY="${DEVIN_API_KEY}"
   export GITHUB_TOKEN="${GITHUB_TOKEN}"
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   **Important**: The env vars must be `export`ed before running uvicorn. Inline `VAR=value command` syntax might not work reliably with `${SECRET}` substitution.

3. The server validates `GITHUB_WEBHOOK_SECRET` is non-empty on startup. If it fails with `RuntimeError: GITHUB_WEBHOOK_SECRET is not configured`, check the export.

## Key Endpoints
- `GET /health` — health check
- `GET /api/stats` — aggregate stats (total PRs, findings by severity, quality/security totals)
- `GET /api/reviews` — list of review records
- `GET /api/reviews/{id}/findings` — individual findings for a review
- `GET /dashboard` — serves the React frontend from `frontend/dist/`
- `POST /webhook/github` — webhook endpoint (requires HMAC signature)

## Data Seeding for Testing

The DB is SQLite at `./data/pr_reviews.db`. For a fresh test, delete it before starting the server.

To seed data from a real Devin session, use a Python script that:
1. Calls `poll_session(session_id)` to get session data
2. Runs `_extract_output()` → `_parse_finding_counts()` → `_parse_findings()`
3. Creates a `ReviewRecord` and `Finding` rows via `async_session()`

## Important: Devin v1 API Response Format

- `structured_output` is often `None` for v1 sessions
- Messages use `"message"` field (not `"content"`)
- Sessions commonly end in `"blocked"` status (waiting_for_user), which means the agent finished but the session is paused — output is available
- Quality findings use `category` (bug, consistency, error-handling, etc.), not `severity`
- Security findings use `severity` (critical, high, medium, low)

## Dashboard Verification

1. **Stat Cards**: Check `Total PRs Reviewed`, `Total Findings` (= security + quality)
2. **Reviews Table**: Shows repo, PR#, status, Security count, Quality count, Latency, Date
3. **Detail Modal**: Click a review row → shows individual findings with category/severity badges, file paths, descriptions, and "Fix This" buttons
4. **Severity Chart**: Pie chart of critical/high/medium/low (empty if all findings are quality-only with categories)

## Running Unit Tests
```bash
python -m pytest tests/ -v
```

## Common Issues
- Port 8000 already in use: `fuser -k 8000/tcp` to free it
- `lsof` might not be available; use `fuser` instead
- If sessions are stuck in "blocked" status, that's expected — the agent produced output but is waiting for human follow-up
