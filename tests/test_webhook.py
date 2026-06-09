"""
Stub tests for the webhook endpoint.

Demonstrates how to test the webhook with a mock payload and mocked
Devin API responses using respx (httpx mock library).

To run:
    pip install pytest pytest-asyncio respx httpx
    pytest tests/
"""

import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app

# Set a known webhook secret for testing
TEST_WEBHOOK_SECRET = "test-secret-123"


def _sign_payload(payload: bytes, secret: str) -> str:
    """Generate a valid X-Hub-Signature-256 header value."""
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _make_pr_payload(
    repo: str = "owner/repo",
    pr_number: int = 42,
    head_sha: str = "abc123def456",
    action: str = "opened",
) -> dict:
    """Build a minimal pull_request webhook payload."""
    return {
        "action": action,
        "pull_request": {
            "number": pr_number,
            "title": "Test PR",
            "body": "A test pull request",
            "head": {"sha": head_sha},
            "user": {"login": "testuser"},
        },
        "repository": {
            "full_name": repo,
        },
    }


@pytest.fixture(autouse=True)
def _override_settings(monkeypatch):
    """Override settings for all tests in this module."""
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "DEVIN_API_KEY", "fake-devin-key")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "fake-github-token")


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature():
    """Webhook should return 403 for an invalid signature."""
    payload = json.dumps(_make_pr_payload()).encode()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalidsignature",
                "X-GitHub-Event": "pull_request",
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_ignores_non_pr_events():
    """Webhook should ignore events that are not pull_request."""
    payload = json.dumps({"action": "created"}).encode()
    signature = _sign_payload(payload, TEST_WEBHOOK_SECRET)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Event ignored"


@pytest.mark.asyncio
async def test_webhook_ignores_non_matching_actions():
    """Webhook should ignore pull_request events with actions other than opened/synchronize."""
    payload_dict = _make_pr_payload(action="closed")
    payload = json.dumps(payload_dict).encode()
    signature = _sign_payload(payload, TEST_WEBHOOK_SECRET)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "pull_request",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Action ignored"


@pytest.mark.asyncio
async def test_webhook_accepts_valid_pr_opened(monkeypatch):
    """Webhook should accept a valid pull_request opened event and return 202.

    Note: In a full test, you would use respx to mock the Devin API and
    GitHub API calls made by the orchestrator background task. For example:

        import respx

        @respx.mock
        async def test_full_flow():
            respx.post("https://api.devin.ai/v1/sessions").respond(
                json={"session_id": "test-session-id"}
            )
            respx.get("https://api.devin.ai/v1/sessions/test-session-id").respond(
                json={"status_enum": "finished", "structured_output": "..."}
            )
            # ... etc
    """
    # Mock the orchestrator to avoid actual API calls
    async def mock_orchestrator(pr_payload: dict) -> None:
        pass

    monkeypatch.setattr(
        "app.routers.webhook.run_orchestrator", mock_orchestrator
    )

    payload_dict = _make_pr_payload()
    payload = json.dumps(payload_dict).encode()
    signature = _sign_payload(payload, TEST_WEBHOOK_SECRET)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "pull_request",
            },
        )
    assert resp.status_code == 202
    assert resp.json()["detail"] == "Review dispatched"
