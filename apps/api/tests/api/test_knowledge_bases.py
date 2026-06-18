from fastapi.testclient import TestClient


def test_create_knowledge_base(client: TestClient, auth_headers: dict):
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "My KB", "description": "Test knowledge base"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "OK"
    assert data["data"]["name"] == "My KB"


def test_list_knowledge_bases(client: TestClient, auth_headers: dict):
    client.post(
        "/api/v1/knowledge-bases",
        json={"name": "KB 1"},
        headers=auth_headers,
    )
    response = client.get("/api/v1/knowledge-bases", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] >= 1


def test_get_knowledge_base_not_found(client: TestClient, auth_headers: dict):
    response = client.get(
        "/api/v1/knowledge-bases/nonexistent-id",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_delete_knowledge_base(client: TestClient, auth_headers: dict):
    create_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "To Delete"},
        headers=auth_headers,
    )
    kb_id = create_resp.json()["data"]["id"]

    delete_resp = client.delete(
        f"/api/v1/knowledge-bases/{kb_id}",
        headers=auth_headers,
    )
    assert delete_resp.status_code == 200

    # Verify it's gone
    get_resp = client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_requires_auth(client: TestClient):
    response = client.get("/api/v1/knowledge-bases")
    assert response.status_code == 401
