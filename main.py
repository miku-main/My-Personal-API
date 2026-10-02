from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import StudySession, StudySessionCreate, GitHubCommit, FeedItem, Stats
from stats import build_stats, build_feed

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="My Personal API", lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Welcome to my personal API"}

@app.get("/me")
def about_me():
    return {
        "name": "Your Name",
        "role": "Student",
        "interests": ["computer science", "cybersecurity"],
    }

@app.post("/study-sessions", response_model=StudySession, status_code=201)
def log_study_session(data: StudySessionCreate, db: Session = Depends(get_session)):
    study_session = StudySession.model_validate(data)
    db.add(study_session)
    db.commit()
    db.refresh(study_session)
    return study_session

@app.get("/study-sessions", response_model=list[StudySession])
def list_study_sessions(db: Session = Depends(get_session)):
    statement = select(StudySession).order_by(StudySession.created_at.desc())
    return db.exec(statement).all()

@app.get("/github/commits", response_model=list[GitHubCommit])
def list_commits(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    statement = (
        select(GitHubCommit)
        .order_by(GitHubCommit.committed_at.desc())
        .limit(limit)
    )
    return db.exec(statement).all()

@app.get("/feed", response_model=list[FeedItem])
def get_feed(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    return build_feed(db, limit)

@app.get("/stats", response_model=Stats)
def get_stats(db: Session = Depends(get_session)):
    return build_stats(db)