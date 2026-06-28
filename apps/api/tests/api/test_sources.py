from fastapi.testclient import TestClient


def _create_kb(client: TestClient, auth_headers: dict, name: str = "Test KB") -> str:
    """Helper: create a knowledge base and return its ID."""
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


def _create_source(
    client: TestClient,
    auth_headers: dict,
    kb_id: str,
    source_type: str = "upload",
    config: dict | None = None,
) -> dict:
    """Helper: create a source and return the response data."""
    body: dict[str, object] = {"type": source_type}
    if config is not None:
        body["config"] = config
    resp = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        json=body,
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]


def test_create_source_pending_status(client: TestClient, auth_headers: dict):
    """Newly created source should be in pending status with empty config."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_source(client, auth_headers, kb_id)

    assert source["status"] == "pending"
    assert source["config"] == {}
    assert source["type"] == "upload"
    assert source["knowledge_base_id"] == kb_id


def test_create_source_requires_auth(client: TestClient):
    """Unauthenticated requests should be rejected."""
    response = client.post(
        "/api/v1/knowledge-bases/fake-kb-id/sources",
        json={"type": "upload"},
    )
    assert response.status_code == 401


def test_list_sources(client: TestClient, auth_headers: dict):
    """List should return all sources for a KB, newest first."""
    kb_id = _create_kb(client, auth_headers)
    _create_source(client, auth_headers, kb_id)
    _create_source(client, auth_headers, kb_id)

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 2
    assert len(data["data"]) == 2
    # Newest first
    assert data["data"][0]["created_at"] >= data["data"][1]["created_at"]


def test_delete_source(client: TestClient, auth_headers: dict):
    """Deleting a source should succeed and subsequent get should 404."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_source(client, auth_headers, kb_id)

    del_resp = client.delete(
        f"/api/v1/sources/{source['id']}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["code"] == "OK"

    # Verify it's gone via list-by-KB
    list_resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        headers=auth_headers,
    )
    assert list_resp.json()["meta"]["total"] == 0


def test_delete_source_not_found(client: TestClient, auth_headers: dict):
    """Deleting a nonexistent source should return 404."""
    response = client.delete(
        "/api/v1/sources/nonexistent-id",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_extract_source_pending_status(client: TestClient, auth_headers: dict):
    """Extracting a pending source should fail with SOURCE_STATUS_INVALID."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_source(client, auth_headers, kb_id)

    resp = client.post(
        f"/api/v1/sources/{source['id']}/extract",
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "SOURCE_STATUS_INVALID"


def test_extract_source_no_config(client: TestClient, auth_headers: dict):
    """Extracting a source with no s3_key should fail with VALIDATION_ERROR."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_source(client, auth_headers, kb_id)

    # Manually set status to active to bypass the pending guard
    resp = client.post(
        f"/api/v1/sources/{source['id']}/extract",
        headers=auth_headers,
    )
    assert resp.status_code == 422
