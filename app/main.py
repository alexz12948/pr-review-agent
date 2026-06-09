import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import webhook, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
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
