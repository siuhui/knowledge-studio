"""Tests for the chat message endpoint."""

import json
from contextlib import AbstractContextManager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _create_kb(client: TestClient, auth_headers: dict, name: str = "Test KB") -> str:
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


def _mock_llm_answer(answer: str = "Mock answer") -> AbstractContextManager[MagicMock]:
    return patch("app.services.chat.llm_provider.generate", return_value=answer)


# ── Send message (auto-create session) ──


def test_send_message_creates_session(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with (
        patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]),
        _mock_llm_answer("Mock RAG answer"),
    ):
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
    assert data["data"]["answer"] == "Mock RAG answer"
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
    with (
        patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]),
        _mock_llm_answer("First answer"),
    ):
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
    with (
        patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]),
        _mock_llm_answer("Follow-up answer"),
    ):
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

    with (
        patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]),
        _mock_llm_answer(),
    ):
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

    with (
        patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]),
        _mock_llm_answer(),
    ):
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
    with (
        patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]),
        _mock_llm_answer(),
    ):
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


# ═══════════════════════════════════════════════════════════════════
# Streaming endpoint tests
# ═══════════════════════════════════════════════════════════════════


async def _token_gen(**kwargs: object) -> str:  # type: ignore[no-any-unimported]
    """Simulated token stream for testing."""
    yield "Hello"
    yield " world"


def _parse_sse_events(response) -> list[dict]:
    """Extract data: JSON objects from an SSE response."""
    events: list[dict] = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            payload = line[6:]
            if payload.strip():
                events.append(json.loads(payload))
    return events


# ── Happy path ──


def test_stream_message_returns_sse_events(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch(
        "app.services.chat.get_async_provider"
    ) as mock_get, patch(
        "app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]
    ):
        mock_provider = mock_get.return_value
        mock_provider.generate_stream = _token_gen

        with client.stream(
            "POST",
            "/api/v1/chat/messages/stream",
            json={
                "knowledge_base_id": kb_id,
                "session_id": None,
                "content": "What is RAG?",
            },
            headers=auth_headers,
        ) as response:
            assert response.status_code == 200
            events = _parse_sse_events(response)

        assert events[0]["type"] == "session"
        assert events[0]["session_id"] != ""
        assert events[0]["user_msg_id"] != ""

        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 2
        assert token_events[0]["text"] == "Hello"
        assert token_events[1]["text"] == " world"

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["persisted"] is True
        assert done_events[0]["ai_message_id"] != ""


def test_stream_message_continues_session(client: TestClient, auth_headers: dict):
    """Second message in an existing session should include history in the prompt."""
    kb_id = _create_kb(client, auth_headers)

    with patch("app.services.chat.get_async_provider") as mock_get, patch(
        "app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]
    ):
        mock_provider = mock_get.return_value
        mock_provider.generate_stream = _token_gen

        # First message creates session
        with client.stream(
            "POST",
            "/api/v1/chat/messages/stream",
            json={"knowledge_base_id": kb_id, "session_id": None, "content": "First"},
            headers=auth_headers,
        ) as resp:
            events1 = _parse_sse_events(resp)
        sess_id = events1[0]["session_id"]

        # Second message
        with client.stream(
            "POST",
            "/api/v1/chat/messages/stream",
            json={"knowledge_base_id": kb_id, "session_id": sess_id, "content": "Second"},
            headers=auth_headers,
        ) as resp:
            events2 = _parse_sse_events(resp)
        assert events2[0]["session_id"] == sess_id


# ── Empty context (no documents) ──


def test_stream_message_no_documents(client: TestClient, auth_headers: dict):
    """When no documents are selected, tokens still stream with chat system prompt."""
    kb_id = _create_kb(client, auth_headers)

    with patch("app.services.chat.get_async_provider") as mock_get:
        mock_provider = mock_get.return_value
        mock_provider.generate_stream = _token_gen

        # reference_document_ids=[] means no retrieval
        with client.stream(
            "POST",
            "/api/v1/chat/messages/stream",
            json={
                "knowledge_base_id": kb_id,
                "session_id": None,
                "content": "Hello",
                "reference_document_ids": [],
            },
            headers=auth_headers,
        ) as response:
            assert response.status_code == 200
            events = _parse_sse_events(response)

        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 2

        citation_events = [e for e in events if e["type"] == "citation"]
        assert len(citation_events) == 1
        assert citation_events[0]["citations"] == []


# ── Error cases ──


def test_stream_message_session_not_found(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with client.stream(
        "POST",
        "/api/v1/chat/messages/stream",
        json={
            "knowledge_base_id": kb_id,
            "session_id": "nonexistent-id",
            "content": "Hello",
        },
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        events = _parse_sse_events(response)

    # Non-existent session → error event conveyed via SSE, not HTTP status
    assert any(e["type"] == "error" for e in events)
    done_events = [e for e in events if e["type"] == "done"]
    assert done_events[-1]["persisted"] is False


def test_stream_message_cross_kb_rejected(client: TestClient, auth_headers: dict):
    kb1_id = _create_kb(client, auth_headers, "KB One")
    kb2_id = _create_kb(client, auth_headers, "KB Two")

    # Create session in KB1
    with patch("app.services.chat.get_async_provider") as mock_get, patch(
        "app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]
    ):
        mock_provider = mock_get.return_value
        mock_provider.generate_stream = _token_gen

        with client.stream(
            "POST",
            "/api/v1/chat/messages/stream",
            json={"knowledge_base_id": kb1_id, "session_id": None, "content": "Q"},
            headers=auth_headers,
        ) as resp:
            events = _parse_sse_events(resp)
        sess_id = events[0]["session_id"]

    # Try to access via KB2 — should get error via SSE, not HTTP
    with client.stream(
        "POST",
        "/api/v1/chat/messages/stream",
        json={"knowledge_base_id": kb2_id, "session_id": sess_id, "content": "Q2"},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        events = _parse_sse_events(response)

    assert any(e["type"] == "error" for e in events)
    done_events = [e for e in events if e["type"] == "done"]
    assert done_events[-1]["persisted"] is False


def test_stream_message_llm_error(client: TestClient, auth_headers: dict):
    """LLM error mid-stream should emit error + done events."""
    kb_id = _create_kb(client, auth_headers)

    async def _error_gen(**kwargs: object) -> str:  # type: ignore[no-any-unimported]
        yield "partial"
        raise RuntimeError("API down")

    with patch("app.services.chat.get_async_provider") as mock_get, patch(
        "app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]
    ):
        mock_provider = mock_get.return_value
        mock_provider.generate_stream = _error_gen

        with client.stream(
            "POST",
            "/api/v1/chat/messages/stream",
            json={"knowledge_base_id": kb_id, "session_id": None, "content": "Q"},
            headers=auth_headers,
        ) as response:
            assert response.status_code == 200
            events = _parse_sse_events(response)

        assert any(e["type"] == "token" and e["text"] == "partial" for e in events)
        assert any(e["type"] == "error" for e in events)
        done_events = [e for e in events if e["type"] == "done"]
        assert done_events[-1]["persisted"] is False


# ── Validation ──


def test_stream_message_empty_content(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    resp = client.post(
        "/api/v1/chat/messages/stream",
        json={"knowledge_base_id": kb_id, "session_id": None, "content": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── Auth required ──


def test_stream_message_requires_auth(client: TestClient):
    resp = client.post(
        "/api/v1/chat/messages/stream",
        json={"knowledge_base_id": "fake-kb", "session_id": None, "content": "Hello"},
    )
    assert resp.status_code == 401
