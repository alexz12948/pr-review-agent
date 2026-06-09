from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEVIN_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/pr_reviews.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
