import os
from datetime import datetime

import httpx
from dotenv import load_dotenv
from sqlmodel import Session

from database import create_db_and_tables, engine
from models import GitHubCommit

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
if not GITHUB_TOKEN or not GITHUB_USERNAME:
    raise RuntimeError("GITHUB_TOKEN and GITHUB_USERNAME must be set in .env")

API_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

def get_all_pages(client, url, params=None):
    items = []
    while url:
        response = client.get(url, headers=HEADERS, params=params)
        if response.status_code == 409: # empty repository, no commits yet
            return []
        response.raise_for_status()
        items.extend(response.json())
        url = response.links.get("next", {}).get("url")
        params = None # the "next" URL already contains the parameters
    return items

def parse_github_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def collect_commits():
    create_db_and_tables()
    new_count = 0
    
    with httpx.Client(headers=HEADERS, timeout=30) as client, Session(engine) as db:
        repos = get_all_pages(
            client,
            f"{API_URL}/user/repos",
            {"affiliation": "owner", "per_page": 100},
        )
        
        for repo in repos:
            commits = get_all_pages(
                client,
                f"{API_URL}/repos/{repo['full_name']}/commits",
                {"author": GITHUB_USERNAME, "per_page": 100},
            )
            
            for item in commits:
                if db.get(GitHubCommit, item["sha"]):
                    continue # already saved, skip it
                
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
        
        db.commit()
    print(f"Saved {new_count} new commits.")
    
if __name__ == "__main__":
    collect_commits()