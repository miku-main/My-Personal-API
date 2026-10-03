"""
GitHub collector: pulls my commit history from the GitHub API and saves it to the database.

Run manually with: python github_collector.py
Safe to run any number of times (idempotent): existing commits are skipped.
"""

import os
from datetime import datetime

import httpx
from dotenv import load_dotenv
from sqlmodel import Session

from database import create_db_and_tables, engine
from models import GitHubCommit

load_dotenv()

# Fine-grained, read-only token with an expiration date (least privilege).
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
if not GITHUB_TOKEN or not GITHUB_USERNAME:
    raise RuntimeError("GITHUB_TOKEN and GITHUB_USERNAME must be set in .env")

API_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    # Pin the API version so GitHub changes can't silently break this script.
    "X-GitHub-Api-Version": "2022-11-28",
}

def get_all_pages(client, url, params=None):
    """
    Fetched every page of a GitHub list endpoint.
    GitHub returns at most 100 items per request and includes a "next" linke
    when there's more.
    """
    items = []
    while url:
        response = client.get(url, headers=HEADERS, params=params)
        if response.status_code == 409: # empty repository, no commits yet
            return []
        
        # Any other error (bad token = 401, rate limit = 403).
        response.raise_for_status()
        items.extend(response.json())
        url = response.links.get("next", {}).get("url")
        params = None # the "next" URL already contains the parameters
    return items

def parse_github_date(value: str) -> datetime:
    # Convert GitHub's '2026-10-02T02:00:00Z' format to a timezone-aware datetime object.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def collect_commits():
    # Save any of my commits that aren't in the database yet.
    create_db_and_tables()
    new_count = 0
    
    # timeout=30: give up after 30 seconds instead of hanging forever.
    with httpx.Client(headers=HEADERS, timeout=30) as client, Session(engine) as db:
        # every repo I own.
        repos = get_all_pages(
            client,
            f"{API_URL}/user/repos",
            {"affiliation": "owner", "per_page": 100},
        )
        
        for repo in repos:
            # Only commits linked to my account
            # This reads each repo's default branch only.
            commits = get_all_pages(
                client,
                f"{API_URL}/repos/{repo['full_name']}/commits",
                {"author": GITHUB_USERNAME, "per_page": 100},
            )
            
            for item in commits:
                # Idempotency: skip commits already saved
                if db.get(GitHubCommit, item["sha"]):
                    continue # already saved, skip it
                
                # Keep only the first line (the summary) of the message.
                # 'or [""]' handles the rare empty commit message.
                message_lines = item["commit"]["message"].splitlines() or [""]
                db.add(
                    GitHubCommit(
                        sha=item["sha"],
                        repo=repo["full_name"],
                        message=message_lines[0][:300],
                        committed_at=parse_github_date(item["commit"]["committer"]["date"]),
                        url=item["html_url"],
                    )
                )
                new_count += 1
        
        # One commit at the end saves everything in a single transaction.
        db.commit()
    print(f"Saved {new_count} new commits.")
    
# Only run when executed directly, not when another file imports this one
# (needed later when we schedule the collector).
if __name__ == "__main__":
    collect_commits()