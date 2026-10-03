"""
Data models: the shape of every table and every API response.

Models with table=True are real database tables.
Models without it only describe data going in or out of the API.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

class StudySessionBase(SQLModel):
    """
    Fields the user is allowed to provide, with validation limits.
    Bad input (empty topic, negative minuts, etc.) is rejected with a 422 error.
    """
    topic: str = Field(min_length=1, max_length=100)
    minutes: int = Field(gt=0, le=720)
    notes: str | None = Field(default=None, max_length=1000)

class StudySession(StudySessionBase, table=True):
    # The database table. Adds fields only the server sets.
    # id comes from a Postgres sequence: always increases, never reused.
    id: int | None = Field(default=None, primary_key=True)
    
    # Always stored in UTC so data stays consistent across time zones.
    # Converted to local time only when grouping by day (check stats.py).
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

class StudySessionCreate(StudySessionBase):
    """
    What the API accepts from outside. Kept separate from the table model to prevent mass assignment:
    a user can't send their own id or a fake created_at.
    """
    pass

class GitHubCommit(SQLModel, table=True):
    # The commit SHA is a natural key: already unique, so the same commit
    # can never be saved twice, even if the collector runs many times.
    sha: str = Field(primary_key=True, max_length=40)
    
    # Indexes make filtering/sorting on these columns fast.
    repo: str = Field(index=True)
    message: str
    committed_at: datetime = Field(sa_type=DateTime(timezone=True), index=True)
    url: str

class FeedItem(SQLModel):
    """
    One common format for every data source in the unified feed.
    Normalizing everything into this shape is what makes aggregation work:
    a new source (sleep, workouts, etc.) only needs a converter to FeedItem.
    """
    type: str
    timestamp: datetime
    title: str
    details: str | None = None
    url: str | None = None

class Stats(SQLModel):
    # Summary metrics reutnred by /stats.
    timezone: str
    study_sessions: int
    study_minnutes: int
    commits: int
    active_days: int
    current_streak: int
    longest_streak: int