"""
Database setup: connects to Postgres (hosted on Neon) 
and hands out sessions to the rest of the app.
"""
import os

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

# Load variables from .env into the environment.
# Secrets live in .env (blocked by .gitignore), never in the code itself

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Fail fast: crash at startup with a message instead of a confusing error later
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Check your .env file.")

# The engine manages connections to the database.
# pool_pre_ping tests each connecion before using it,
# Neon's free tier sleeps when idle and drops old connections.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def create_db_and_tables():
    # Create any tables that don't exist yet.
    SQLModel.metadata.create_all(engine)

def get_session():
    # Give each request its own database session.
    with Session(engine) as session:
        yield session