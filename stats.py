import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlmodel import Session, select, func

from models import FeedItem, GitHubCommit, StudySession, Stats

load_dotenv()

TIMEZONE_NAME = os.getenv("TIMEZONE", "UTC")
LOCAL_TZ = ZoneInfo(TIMEZONE_NAME)

def to_local_date(moment: datetime) -> date:
    return moment.astimezone(LOCAL_TZ).date()

def build_feed(db: Session, limit: int) -> list[FeedItem]:
    sessions = db.exec(
        select(StudySession)
        .order_by(StudySession.created_at.desc())
        .limit(limit)
    ).all()
    commits = db.exec(
        select(GitHubCommit)
        .order_by(GitHubCommit.committed_at.desc())
        .limit(limit)
    ).all()
    
    items = [
        FeedItem(
            type="study",
            timestamp=s.created_at,
            title=f"Studied {s.topic} for {s.minutes} minutes",
            details=s.notes,
        )
        for s in sessions
    ] 
    items += [
        FeedItem(
            type="commit",
            timestamp=c.committed_at,
            title=c.message,
            details=c.repo,
            url=c.url,
        )
        for c in commits
    ]
    
    items.sort(key=lambda item: item.timestamp, reverse=True)
    return items[:limit]

def caluculate_streaks(active_days: set[date], today: date) -> tuple[int, int]:
    if not active_days:
        return 0, 0
    
    longest = 0
    run = 0
    previous = None
    
    for day in sorted(active_days):
        run = run + 1 if previous == day - timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
        
    current = 0
    day = today if today in active_days else today - timedelta(days=1)
    while day in active_days:
        current += 1
        day -= timedelta(days=1)
    
    return current, longest

def build_stats(db: Session) -> Stats:
    session_count = db.exec(select(func.count()).select_from(StudySession)).one()
    study_minutes = db.exec(select(func.coalesce(func.sum(StudySession.minutes), 0))).one()
    commit_count = db.exec(select(func.count()).select_from(GitHubCommit)).one()
    
    timestamps = list(db.exec(select(StudySession.created_at)).all())
    timestamps += db.exec(select(GitHubCommit.committed_at)).all()
    active_days = {to_local_date(t) for t in timestamps}
    
    today = datetime.now(LOCAL_TZ).date()
    current_streak, longest_streak = caluculate_streaks(active_days, today)
    
    return Stats(
        timezone=TIMEZONE_NAME,
        study_sessions=session_count,
        study_minnutes=study_minutes,
        commits=commit_count,
        active_days=len(active_days),
        current_streak=current_streak,
        longest_streak=longest_streak,
    )
    
    