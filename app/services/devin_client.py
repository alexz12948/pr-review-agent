import asyncio

import httpx

from app.config import settings

DEVIN_API_BASE = "https://api.devin.ai/v1"


async def create_session(prompt: str) -> str:
    """Create a new Devin session with the given prompt. Returns session_id."""
    url = f"{DEVIN_API_BASE}/sessions"
    headers = {
        "Authorization": f"Bearer {settings.DEVIN_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json={"prompt": prompt}, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data["session_id"]


async def poll_session(session_id: str, timeout: int = 600, interval: int = 10) -> dict:
    """Poll a Devin session until it reaches a terminal state.

    Returns the full response once status_enum is in ("finished", "stopped", "failed").
    Raises TimeoutError if the deadline is exceeded.
    """
    url = f"{DEVIN_API_BASE}/sessions/{session_id}"
    headers = {
        "Authorization": f"Bearer {settings.DEVIN_API_KEY}",
    }
    terminal_states = {"finished", "stopped", "failed"}
    elapsed = 0

    async with httpx.AsyncClient() as client:
        while elapsed < timeout:
            resp = await client.get(url, headers=headers, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status_enum") in terminal_states:
                return data

            await asyncio.sleep(interval)
            elapsed += interval

    raise TimeoutError(
        f"Session {session_id} did not complete within {timeout} seconds"
    )


async def send_message(session_id: str, message: str) -> dict:
    """Send a message to an existing Devin session."""
    url = f"{DEVIN_API_BASE}/session/{session_id}/message"
    headers = {
        "Authorization": f"Bearer {settings.DEVIN_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json={"message": message}, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
