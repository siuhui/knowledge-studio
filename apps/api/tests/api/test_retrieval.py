from unittest.mock import patch

from fastapi.testclient import TestClient


def test_retrieval_query_empty_kb(client: TestClient, auth_headers: dict):
    """Search against an empty knowledge base should return empty results."""
    # Create a KB first
    create_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Empty KB"},
        headers=auth_headers,
    )
    kb_id = create_resp.json()["data"]["id"]

    # Mock the embedder — this test exercises the search path without
    # calling the real embedding API.
    with patch("app.services.embedding.embedder.embed", return_value=[[0.0] * 1024]):
        response = client.post(
            "/api/v1/retrieval/query",
            json={"query": "test query", "knowledge_base_id": kb_id, "top_k": 5},
            headers=auth_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "OK"
    assert data["data"]["results"] == []


def test_retrieval_requires_auth(client: TestClient):
    response = client.post(
        "/api/v1/retrieval/query",
        json={"query": "test", "knowledge_base_id": "some-id"},
    )
    assert response.status_code == 401
