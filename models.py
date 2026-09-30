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