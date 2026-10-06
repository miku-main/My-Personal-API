"""
Integration tests: real HTTP requests through the full app
(routing, validation, authentication, database), using the test database.
"""
from datetime import datetime, timezone

import anthropic
import httpx
import pytest

import main
from models import AskResponse, GitHubCommit

PRIVATE_ENDPOINTS = [
    ("get", "/feed"),
    ("get", "/study-sessions"),
    ("get", "/github/commits"),
    ("post", "/study-sessions"),
    ("post", "/ask"),
]

# Authentication
def test_public_endpoints_work_without_a_key(client):
    assert client.get("/").status_code == 200
    assert client.get("/me").status_code == 200
    assert client.get("/stats").status_code == 200
    
# parametrize runs this one test once per endpoint in the list.
@pytest.mark.parametrize("method, path", PRIVATE_ENDPOINTS)
def test_private_endpoints_reject_missing_key(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401

@pytest.mark.parametrize("method, path", PRIVATE_ENDPOINTS)
def test_private_endpoints_reject_wrong_key(client, method, path):
    response = getattr(client, method)(path, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
    
    
# Study sessions
def test_log_study_session(client, auth):
    response = client.post(
        "/study-sessions",
        json={"topic": "Subnetting", "minutes": 45, "notes": "CIDR practice"},
        headers=auth,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["topic"] == "Subnetting"
    assert body["minutes"] == 45
    assert body["id"] is not None
    assert body["created_at"] is not None
    
@pytest.mark.parametrize(
    "bad_input",
    [
        {"topic": "Subnetting", "minutes": -5},  # negative minutes
        {"topic": "Subnetting", "minutes": 0},  # zero minutes
        {"topic": "Subnetting", "minutes": 721},  # over 12 hours
        {"topic": "", "minutes": 30},  # empty topic
        {"minutes": 30},  # missing topic
    ],
)
def test_invalid_study_session_is_rejected(client, auth, bad_input):
    response = client.post("/study-sessions", json=bad_input, headers=auth)
    assert response.status_code == 422
    
def test_client_cannot_set_server_fields(client, auth):
    # Mass assignment check: sending our own id and created_at is ignored.
    response = client.post(
        "/study-sessions",
        json={
            "topic": "Ports",
            "minutes": 20,
            "id": 999,
            "created_at": "2000-01-01T00:00:00Z",
        },
        headers=auth,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] != 999
    assert not body["created_at"].startswith("2000")
    
# Feed and stats
def test_feed_merges_sources_newest_first(client, auth, db):
    db.add(
        GitHubCommit(
            sha="a" * 40,
            repo="me/old-project",
            message="Old commit",
            committed_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            url="https://github.com/me/old-project/commit/aaa",
        )
    )
    db.commit()
    client.post("/study-sessions", json={"topic": "DNS", "minutes": 30}, headers=auth)
    feed = client.get("/feed", headers=auth).json()
    assert [item["type"] for item in feed] == ["study", "commit"]
    
def test_stats_totals(client, auth):
    client.post("/study-sessions", json={"topic": "DNS", "minutes": 30}, headers=auth)
    client.post("/study-sessions", json={"topic": "DHCP", "minutes": 45}, headers=auth)
    
    stats = client.get("/stats").json()
    
    assert stats["study_sessions"] == 2
    assert stats["study_minutes"] == 75
    assert stats["active_days"] == 1
    assert stats["current_streak"] == 1
    
def test_stats_empty_database(client):
    stats = client.get("/stats").json()
    assert stats["study_sessions"] == 0
    assert stats["study_minutes"] == 0
    assert stats["current_streak"] == 0
    
# AI assistant
def test_ask_returns_answer(client, auth, monkeypatch):
    def fake_ask(db, question):
        return AskResponse(answer="Fake answer", model="fake", input_tokens=1, output_tokens=1)
    
    # Replace the real function only for this test.
    monkeypatch.setattr(main, "ask_assistant", fake_ask)
    
    response = client.post("/ask", json={"question": "Hi"}, headers=auth)
    
    assert response.status_code == 200
    assert response.json()["answer"] == "Fake answer"
    
def test_ask_returns_502_when_ai_is_down(client, auth, monkeypatch):
    def failing_ask(db, question):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.APIConnectionError(request=request)
    
    monkeypatch.setattr(main, "ask_assistant", failing_ask)
    
    response = client.post("/ask", json={"question": "Hi"}, headers=auth)
    
    assert response.status_code == 502
    # Provider details must not leak to the client.
    assert response.json()["detail"] == "AI service unavailable"
    
def test_ask_rejects_long_question_before_spending_money(client, auth, monkeypatch):
    calls = []
    monkeypatch.setattr(main, "ask_assistant", lambda db, q: calls.append(q))
    
    response = client.post("/ask", json={"question": "x" * 501}, headers=auth)
    
    assert response.status_code == 422
    assert calls == [] # the AI was never called