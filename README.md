# PR Review Agent

An automated pull request analysis and remediation system. It leverages AI agents (via the Devin API) to perform multi-perspective code reviews—targeting security and code quality—and provides an interactive dashboard to review findings and trigger automated fixes.

## How It Works

The agent operates through a structured pipeline triggered by GitHub activity:

1. **Ingestion**: A `/webhook/github` endpoint receives a `pull_request` event and validates the payload using HMAC-SHA256 signatures.
2. **Orchestration**: The system fetches the PR diff and dispatches parallel Devin sessions — one for **Security** and one for **Quality**.
3. **Synthesis**: A third AI session synthesizes the individual reports into a unified set of findings, persisted to SQLite.
4. **Reporting**: Findings are posted back to the GitHub PR as a summary comment and surfaced in the local React dashboard.
5. **Remediation**: Users can trigger "Fix Actions" from the dashboard, spawning a Devin session to generate and commit code fixes directly to the branch.

```mermaid
graph TD
  subgraph "External Ecosystem"
    GH["GitHub API / Webhooks"]
    D_API["Devin AI API"]
  end

  subgraph "PR Review Agent"
    WEB["webhook.py (FastAPI Router)"]
    ORCH["orchestrator.py (Service)"]
    FIX_ORCH["fix_orchestrator.py (Service)"]
    DB[("pr_reviews.db (SQLite/SQLModel)")]
    DASH["dashboard.py (API & React UI)"]
  end

  GH -- "Webhook Event" --> WEB
  WEB -- "Dispatch" --> ORCH
  ORCH -- "create_session" --> D_API
  ORCH -- "get_pr_diff" --> GH
  ORCH -- "Persist ReviewRecord" --> DB
  DASH -- "Read Stats/Reviews" --> DB
  DASH -- "Trigger Fix" --> FIX_ORCH
  FIX_ORCH -- "execute_fix" --> D_API
  FIX_ORCH -- "post_review_comment" --> GH
```

## Tech Stack

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Backend** | Python 3.12+, FastAPI | API framework and request routing |
| **Database** | SQLite + SQLModel | Async persistence of review records and findings |
| **Frontend** | React + Vite | Dashboard for visualizing PR metrics and managing fixes |
| **AI Engine** | Devin API | Autonomous agent execution for analysis and coding tasks |
| **Integration** | GitHub REST API | Source code retrieval and PR commenting |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+ (for frontend)
- SQLite

### Environment Configuration

Copy `.env.example` to `.env` and populate the following variables:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DEVIN_API_KEY` | Bearer token for authenticating with the Devin API | `""` |
| `GITHUB_TOKEN` | Personal Access Token for reading PR diffs and posting comments | `""` |
| `GITHUB_WEBHOOK_SECRET` | Secret key for verifying HMAC-SHA256 signatures from GitHub | `""` |
| `DATABASE_URL` | SQLAlchemy connection string for the SQLite database | `sqlite+aiosqlite:///./data/pr_reviews.db` |

### GitHub Token Permissions

The `GITHUB_TOKEN` is used to read PR diffs/metadata and to post review comments (see `app/services/github_client.py`). Grant it the following:

- **Classic PAT:** the `repo` scope (covers reading diffs and posting comments).
- **Fine-grained PAT:** `Pull requests: Read and write` (post comments) and `Contents: Read-only` (read diffs/metadata), scoped to the repositories you want reviewed.

> Note: the agent does **not** push code fixes using this token — remediation commits are made by the Devin session, not via the GitHub API.

### GitHub Webhook Setup

The `/webhook/github` endpoint ingests PR events. To register it:

1. Go to your repository's **Settings → Webhooks → Add webhook**.
2. **Payload URL:** `https://<your-host>/webhook/github`
3. **Content type:** `application/json`
4. **Secret:** the same value as `GITHUB_WEBHOOK_SECRET`. This is required — the app verifies the `X-Hub-Signature-256` header using HMAC-SHA256 and rejects unsigned or mismatched payloads, and it fails to start if the secret is unset.
5. **Events:** select **Pull requests** only. The handler processes `pull_request` events with the `opened` and `synchronize` actions; all other events and actions are ignored.

### Local Development with ngrok

GitHub cannot reach a server running on `localhost`, so for local development you need to expose your backend with a tunneling tool such as [ngrok](https://ngrok.com/):

```bash
ngrok http 8000
```

Use the generated public URL as the webhook Payload URL (e.g. `https://<subdomain>.ngrok.io/webhook/github`). The URL changes each time you restart ngrok (unless you use a reserved domain), so update the webhook configuration accordingly.

### Local Development

**Backend:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in secrets
mkdir -p data
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run build
```

### Docker

The project ships a multi-stage `Dockerfile` that builds the React frontend and packages it with the FastAPI backend into a single image.

```bash
docker compose up --build
```

- The app is available at `http://localhost:8000`.
- The SQLite database is persisted via the `dbdata` named volume.

## Running Tests

```bash
pytest
```

Test coverage includes webhook signature verification, review orchestration, and fix workflow state transitions.
