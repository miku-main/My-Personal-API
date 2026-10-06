"""
Feed and stats logic: combines all data source into one timeline and calculates my metrics (totals, active days, streaks).
Kept separate from main.py: main.py handles the web layer, this file does the actual work and can be reused elsewhere.
"""
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlmodel import Session, select, func

from models import FeedItem, GitHubCommit, StudySession, Stats

load_dotenv()

# Data is stored in UTC, but "days" must follow my calendar. 
# Otherwise late-night activity lands on the wrong date and breaks streaks. 
# (Windows needs the tzdata package for this to work.)
TIMEZONE_NAME = os.getenv("TIMEZONE", "UTC")
LOCAL_TZ = ZoneInfo(TIMEZONE_NAME)

def to_local(moment: datetime) -> datetime:
    """Convert a stored timestamp to my local time zone.
    Everything is stored in UTC. Some databases drop the time zone and return a "naive" datetime. 
    A naive datetime would otherwise be treated as the COMPUTER's local time,
    which differs between my Mac, Windows, and servers. So naive values are explicitly marked UTC.
    (This hidden assumption was found by writing tests.)
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(LOCAL_TZ)

def to_local_date(moment: datetime) -> date:
    # The calender date of a timestamp in my time zone.
    return to_local(moment).date()

def build_feed(db: Session, limit: int) -> list[FeedItem]:
    """
    Merge every data source into one timeline, newest first.
    Only the newest 'limit' rows are fetched from each source
    That's always enough: even if all top items came from one source, 
    they'd be within that source's newest 'limit'. So we never load the whole library
    """
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
    
    # Normalize each source into the common FeedItem format
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
    
    items.sort(key=lambda item: to_local(item.timestamp), reverse=True)
    return items[:limit]

def calculate_streaks(active_days: set[date], today: date) -> tuple[int, int]:
    # Return (current_streak, longest_streak) in days.
    if not active_days:
        return 0, 0
    
    # Longest streak: walk through days in order. A day right after the previous one extends the run
    longest = 0
    run = 0
    previous = None
    
    for day in sorted(active_days):
        run = run + 1 if previous == day - timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    
    # Current streak: count backward from today.
    # Design choice: if nothing is logged yet today, start from yesterday,
    # so the streak doesn't show 0 every morning before I log anything.
    current = 0
    day = today if today in active_days else today - timedelta(days=1)
    while day in active_days:
        current += 1
        day -= timedelta(days=1)
    
    return current, longest

def build_stats(db: Session) -> Stats:
    # Calculate all summary metrics.
    # Let the DATABASE count and sum (SQL aggregates) so only one number comes back,
    # Instead of sending every row to Python.
    session_count = db.exec(select(func.count()).select_from(StudySession)).one()
    # coalesce(..., 0) returns 0 instead of None if there are no sessions
    study_minutes = db.exec(select(func.coalesce(func.sum(StudySession.minutes), 0))).one()
    commit_count = db.exec(select(func.count()).select_from(GitHubCommit)).one()
    
    # Only the timestamp columns are fetched, not whole rows.
    timestamps = list(db.exec(select(StudySession.created_at)).all())
    timestamps += db.exec(select(GitHubCommit.committed_at)).all()
    
    # A set removes duplicates: 10 commits on one day = 1 active day.
    # That's why this metric can't be inflated by lots of tiny commits.
    active_days = {to_local_date(t) for t in timestamps}
    
    today = datetime.now(LOCAL_TZ).date()
    current_streak, longest_streak = calculate_streaks(active_days, today)
    
    return Stats(
        timezone=TIMEZONE_NAME,
        study_sessions=session_count,
        study_minutes=study_minutes,
        commits=commit_count,
        active_days=len(active_days),
        current_streak=current_streak,
        longest_streak=longest_streak,
    )
    
    