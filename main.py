"""
Personal API

Defines the URLs (endpoints), their parameters, and what they return.
The real logic lives in other files (stats.py, github_collector.py).

Run with: uvicorn main:app --reload
Docs at: http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

import anthropic
from fastapi import Depends, FastAPI, Query, APIRouter, HTTPException
from assisant import ask_assistant

from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import StudySession, StudySessionCreate, GitHubCommit, FeedItem, Stats, AskRequest, AskResponse
from security import require_api_key
from stats import build_stats, build_feed

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts: make sure all tables exist.
    create_db_and_tables()
    yield

app = FastAPI(title="My Personal API", lifespan=lifespan)

# Every route addded to this router requires a valid API key.
# Enforcing auth in one place means a new private endpoint can't accidentally be left unprotected.
private = APIRouter(dependencies=[Depends(require_api_key)], tags=["Private"])

# Public: Basic info and aggregate numbers only, no personal details

@app.get("/", tags=["Public"])
def root():
    return {"message": "Welcome to my personal API"}

@app.get("/me", tags=["Public"])
def about_me():
    return {
        "name": "Gui Sen Zou",
        "role": "Recent Computer Science Graduate",
        "interests": ["computer science", "cybersecurity", "video games", "anime"],
    }
    
@app.get("/stats", response_model=Stats, tags=["Public"])
def get_stats(db: Session = Depends(get_session)):
    # Summary metrics: totals, active days, streaks.
    return build_stats(db)

# Private: requires the X-API-Key header. All personal data is here.

# Study sessions
# 201 = "Created", the correct status code when something new is saved.
@private.post("/study-sessions", response_model=StudySession, status_code=201)
def log_study_session(data: StudySessionCreate, db: Session = Depends(get_session)):
    """
    Log a new study session.
    Accepts StudySessionCreate (validated user input only), then converts it
    into a table row. The server sets id and created_at.
    """
    study_session = StudySession.model_validate(data)
    db.add(study_session)
    db.commit()
    db.refresh(study_session)   # reload to get the new id and created_at
    return study_session

@private.get("/study-sessions", response_model=list[StudySession])
def list_study_sessions(db: Session = Depends(get_session)):
    # All study sessions, newest first. Private: inclues my notes.
    statement = select(StudySession).order_by(StudySession.created_at.desc())
    return db.exec(statement).all()

# GitHub commits

@private.get("/github/commits", response_model=list[GitHubCommit])
def list_commits(
    # Capped at 100 so nobody can request a huge response and slow the API.
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    """
    Newest commits, e.g. /github/commits?limit=5
    
    Private: the token can read private repos, so this could otherwise expose private repo names and commit messages.
    """
    statement = (
        select(GitHubCommit)
        .order_by(GitHubCommit.committed_at.desc())
        .limit(limit)
    )
    return db.exec(statement).all()

# Unified feed and stats

@private.get("/feed", response_model=list[FeedItem])
def get_feed(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    # Everything I've done, from every source, as one timeline.
    # Private: contains study notes and commit details.
    return build_feed(db, limit)

@private.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(get_session)):
    """
    Ask my AI assistant a question about my data.
    Private: every question costs money (prevents "denital of wallet").
    """
    try:
        return ask_assistant(db, request.question)
    except anthropic.APIError:
        # Don't leak provider error details to the client.
        raise HTTPException(status_code=502, detail="AI service unavailable")

# Must come after the private routes are defined: inclue_router copies the routes into the main app.
app.include_router(private)