import os

from pydantic_settings import BaseSettings

# Compiled Vite assets (JS/CSS) live under frontend/dist; the dashboard route
# serves index.html and these assets are mounted under /static.
FRONTEND_DIST = os.path.join("frontend", "dist")
FRONTEND_INDEX = os.path.join(FRONTEND_DIST, "index.html")


class Settings(BaseSettings):
    DEVIN_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/pr_reviews.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
