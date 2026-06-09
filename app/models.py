from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class ReviewRecord(SQLModel, table=True):
    __tablename__ = "review_records"
    __table_args__ = (
        UniqueConstraint("repo", "pr_number", "head_sha", name="uq_repo_pr_sha"),
        {"sqlite_autoincrement": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    repo: str
    pr_number: int
    head_sha: str
    security_findings: int = 0
    quality_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    latency_seconds: float = 0.0
    orchestrator_session_id: str = ""
    security_session_id: str = ""
    quality_session_id: str = ""
    status: str = "success"  # "success" | "partial" | "failed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

