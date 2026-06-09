import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.routers import webhook, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if the webhook secret is not configured: an empty secret would
    # allow an attacker to forge a valid signature and bypass verification.
    if not settings.GITHUB_WEBHOOK_SECRET:
        raise RuntimeError(
            "GITHUB_WEBHOOK_SECRET is not configured. Set it before starting the app."
        )
    # Ensure the data/ directory exists for the SQLite file
    os.makedirs("data", exist_ok=True)
    await init_db()
    yield


app = FastAPI(title="PR Review Agent", lifespan=lifespan)

app.include_router(webhook.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
