from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

class StudySessionBase(SQLModel):
    topic: str = Field(min_length=1, max_length=100)
    minutes: int = Field(gt=0, le=720)
    notes: str | None = Field(default=None, max_length=1000)

class StudySession(StudySessionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

class StudySessionCreate(StudySessionBase):
    pass

class GitHubCommit(SQLModel, table=True):
    sha: str = Field(primary_key=True, max_length=40)
    repo: str = Field(index=True)
    message: str
    committed_at: datetime = Field(sa_type=DateTime(timezone=True), index=True)
    url: str

class FeedItem(SQLModel):
    type: str
    timestamp: datetime
    title: str
    details: str | None = None
    url: str | None = None

class Stats(SQLModel):
    timezone: str
    study_sessions: int
    study_minnutes: int
    commits: int
    active_days: int
    current_streak: int
    longest_streak: int