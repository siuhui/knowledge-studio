"""Tests for the chat message endpoint."""

from unittest.mock import patch

from fastapi.testclient import TestClient


def _create_kb(client: TestClient, auth_headers: dict, name: str = "Test KB") -> str:
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


# ── Send message (auto-create session) ──


def test_send_message_creates_session(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]):
        resp = client.post(
            "/api/v1/chat/messages",
            json={
                "knowledge_base_id": kb_id,
                "session_id": None,
                "content": "What is RAG?",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert data["data"]["session_id"] != ""
    assert data["data"]["answer"] != ""
    assert data["data"]["persisted"] is True

    # Verify session was created and is listed
    sess_id = data["data"]["session_id"]
    list_resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions?page=1&page_size=20",
        headers=auth_headers,
    )
    sessions = list_resp.json()["data"]
    assert any(s["id"] == sess_id for s in sessions)

    # Verify session has 2 messages (user + assistant)
    get_resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        headers=auth_headers,
    )
    msgs = get_resp.json()["data"]["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_send_message_continues_session(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    # First message creates session
    with patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]):
        resp1 = client.post(
            "/api/v1/chat/messages",
            json={
                "knowledge_base_id": kb_id,
                "session_id": None,
                "content": "First question",
            },
            headers=auth_headers,
        )
    sess_id = resp1.json()["data"]["session_id"]

    # Second message in same session
    with patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]):
        resp2 = client.post(
            "/api/v1/chat/messages",
            json={
                "knowledge_base_id": kb_id,
                "session_id": sess_id,
                "content": "Follow-up question",
            },
            headers=auth_headers,
        )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["session_id"] == sess_id

    # Verify 4 messages total
    get_resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        headers=auth_headers,
    )
    msgs = get_resp.json()["data"]["messages"]
    assert len(msgs) == 4
    assert msgs[2]["content"] == "Follow-up question"


# ── Auto-naming ──


def test_send_message_auto_names_session(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]):
        resp = client.post(
            "/api/v1/chat/messages",
            json={
                "knowledge_base_id": kb_id,
                "session_id": None,
                "content": "Explain retrieval augmented generation in detail",
            },
            headers=auth_headers,
        )
    sess_id = resp.json()["data"]["session_id"]

    # Session title should be set from first query
    get_resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sessions/{sess_id}",
        headers=auth_headers,
    )
    title = get_resp.json()["data"]["title"]
    assert title != "New Chat"
    assert "Explain retrieval augmented generation" in title


# ── Session not found ──


def test_send_message_session_not_found(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]):
        resp = client.post(
            "/api/v1/chat/messages",
            json={
                "knowledge_base_id": kb_id,
                "session_id": "nonexistent-session-id",
                "content": "Hello",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 404
    assert resp.json()["code"] == "SESSION_NOT_FOUND"


# ── Cross-KB access via chat ──


def test_send_message_cross_kb_session(client: TestClient, auth_headers: dict):
    kb1_id = _create_kb(client, auth_headers, "KB One")
    kb2_id = _create_kb(client, auth_headers, "KB Two")

    # Create session in KB1
    with patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]):
        resp = client.post(
            "/api/v1/chat/messages",
            json={
                "knowledge_base_id": kb1_id,
                "session_id": None,
                "content": "Question in KB1",
            },
            headers=auth_headers,
        )
    sess_id = resp.json()["data"]["session_id"]

    # Try to continue session via KB2
    with patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]):
        resp = client.post(
            "/api/v1/chat/messages",
            json={
                "knowledge_base_id": kb2_id,
                "session_id": sess_id,
                "content": "Access via KB2",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 403
    assert resp.json()["code"] == "SESSION_ACCESS_DENIED"


# ── Validation ──


def test_send_message_empty_content(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    resp = client.post(
        "/api/v1/chat/messages",
        json={
            "knowledge_base_id": kb_id,
            "session_id": None,
            "content": "",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── Auth required ──


def test_send_message_requires_auth(client: TestClient):
    resp = client.post(
        "/api/v1/chat/messages",
        json={
            "knowledge_base_id": "fake-kb",
            "session_id": None,
            "content": "Hello",
        },
    )
    assert resp.status_code == 401
