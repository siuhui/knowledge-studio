"""Tests for session CRUD endpoints."""

from fastapi.testclient import TestClient


# ── Helpers ──

def _create_kb(client: TestClient, auth_headers: dict, name: str = "Test KB") -> str:
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


def _create_session(
    client: TestClient, auth_headers: dict, kb_id: str, content: str = "Hello"
) -> str:
    """Create a session by sending a chat message (auto-creates session)."""
    from unittest.mock import patch

    mock_embed = [[0.0] * 1024]
    with patch("app.services.embedding.embedder.embed", return_value=mock_embed):
        resp = client.post(
            "/api/v1/chat/messages",
            json={"knowledge_base_id": kb_id, "session_id": None, "content": content},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    return resp.json()["data"]["session_id"]


# ── List sessions ──


def test_list_sessions_empty(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions?page=1&page_size=20",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert data["data"] == []
    assert data["meta"]["total"] == 0


def test_list_sessions_with_items(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    sess_id = _create_session(client, auth_headers, kb_id, "First question")

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions?page=1&page_size=20",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == sess_id
    assert data["data"][0]["message_count"] == 2  # user + assistant
    assert data["data"][0]["last_message_at"] is not None


def test_list_sessions_pagination(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    # Create 3 sessions
    for i in range(3):
        _create_session(client, auth_headers, kb_id, f"Question {i}")

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions?page=1&page_size=2",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 2
    assert data["meta"]["total"] == 3
    assert data["meta"]["total_pages"] == 2


# ── Get session ──


def test_get_session(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    sess_id = _create_session(client, auth_headers, kb_id, "What is RAG?")

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert data["data"]["id"] == sess_id
    assert len(data["data"]["messages"]) == 2
    assert data["data"]["messages"][0]["role"] == "user"
    assert data["data"]["messages"][0]["content"] == "What is RAG?"
    assert data["data"]["messages"][1]["role"] == "assistant"


def test_get_session_not_found(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/nonexistent-id",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "SESSION_NOT_FOUND"


# ── Rename session ──


def test_rename_session(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    sess_id = _create_session(client, auth_headers, kb_id, "Initial query")

    resp = client.patch(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        json={"title": "Custom Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Custom Title"

    # Verify persisted
    get_resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        headers=auth_headers,
    )
    assert get_resp.json()["data"]["title"] == "Custom Title"


def test_rename_session_empty_title(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    sess_id = _create_session(client, auth_headers, kb_id, "Test")

    resp = client.patch(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        json={"title": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── Delete session ──


def test_delete_session(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    sess_id = _create_session(client, auth_headers, kb_id, "Temp chat")

    resp = client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == "OK"

    # Verify deleted
    get_resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404


# ── Cross-KB access ──


def test_session_cross_kb_access_denied(client: TestClient, auth_headers: dict):
    kb1_id = _create_kb(client, auth_headers, "KB One")
    kb2_id = _create_kb(client, auth_headers, "KB Two")

    sess_id = _create_session(client, auth_headers, kb1_id, "Question in KB1")

    # Try to access session from KB1 via KB2 URL
    resp = client.get(
        f"/api/v1/knowledge-bases/{kb2_id}/sessions/{sess_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "SESSION_ACCESS_DENIED"


# ── Auth required ──


def test_list_sessions_requires_auth(client: TestClient):
    resp = client.get("/api/v1/knowledge-bases/fake-id/sessions")
    assert resp.status_code == 401


def test_get_session_requires_auth(client: TestClient):
    resp = client.get("/api/v1/knowledge-bases/fake-id/sessions/fake-session")
    assert resp.status_code == 401


def test_rename_session_requires_auth(client: TestClient):
    resp = client.patch(
        "/api/v1/knowledge-bases/fake-id/sessions/fake-session",
        json={"title": "Hacked"},
    )
    assert resp.status_code == 401


def test_delete_session_requires_auth(client: TestClient):
    resp = client.delete("/api/v1/knowledge-bases/fake-id/sessions/fake-session")
    assert resp.status_code == 401
