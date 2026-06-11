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
    status: str = "pending"  # "pending" | "success" | "partial" | "failed"
    fix_actions_count: int = 0
    has_pending_fixes: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Finding(SQLModel, table=True):
    __tablename__ = "findings"

    id: Optional[int] = Field(default=None, primary_key=True)
    review_id: int = Field(foreign_key="review_records.id")
    agent_type: str  # "security" | "quality"
    severity: Optional[str] = None  # "critical" | "high" | "medium" | "low" | "info"
    category: Optional[str] = None  # "bug" | "inconsistency" | "test-gap" | "style"
    title: str
    description: str
    file: Optional[str] = None
    line: Optional[int] = None
    raw_json: str  # Full original JSON of this finding for context
    fix_status: str = "pending"  # "pending" | "in_progress" | "fixed" | "failed" | "skipped"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FixAction(SQLModel, table=True):
    __tablename__ = "fix_actions"

    id: Optional[int] = Field(default=None, primary_key=True)
    review_id: int = Field(foreign_key="review_records.id")
    finding_ids: str  # JSON array of Finding IDs being addressed, e.g. "[1,2,3]"
    scope: str  # "single" | "all_review" | "by_severity" | "by_agent"
    devin_session_id: Optional[str] = None
    status: str = "queued"  # "queued" | "in_progress" | "completed" | "failed"
    result_summary: Optional[str] = None  # Summary of what Devin did
    commit_sha: Optional[str] = None  # The commit SHA pushed by Devin, if any
    fix_pr_url: Optional[str] = None  # URL of the fix PR or commit, if created
    latency_seconds: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

