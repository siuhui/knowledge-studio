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


def _create_pending_source(client: TestClient, auth_headers: dict, kb_id: str) -> dict:
    """Helper: create a pending source and return the response data."""
    resp = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        json={"type": "upload"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]


def test_presign_requires_auth(client: TestClient):
    """Presign endpoint should reject unauthenticated requests."""
    response = client.post(
        "/api/v1/sources/fake-id/uploads/presign",
        json={"filename": "test.pdf", "content_type": "application/pdf"},
    )
    assert response.status_code == 401


def test_presign_source_not_found(client: TestClient, auth_headers: dict):
    """Presign for a nonexistent source should return 404."""
    response = client.post(
        "/api/v1/sources/nonexistent-id/uploads/presign",
        json={"filename": "test.pdf", "content_type": "application/pdf"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_presign_rejects_bad_extension(client: TestClient, auth_headers: dict):
    """Presign should reject files with unsupported extensions."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_pending_source(client, auth_headers, kb_id)

    response = client.post(
        f"/api/v1/sources/{source['id']}/uploads/presign",
        json={"filename": "malware.exe", "content_type": "application/x-msdownload"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "DOCUMENT_UNSUPPORTED_FORMAT"


def test_presign_validates_extension_empty_name(client: TestClient, auth_headers: dict):
    """Presign should reject filenames that sanitize to empty."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_pending_source(client, auth_headers, kb_id)

    response = client.post(
        f"/api/v1/sources/{source['id']}/uploads/presign",
        json={"filename": ".pdf", "content_type": "application/pdf"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_presign_returns_valid_response(client: TestClient, auth_headers: dict):
    """Presign should return a valid presigned POST URL and fields."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_pending_source(client, auth_headers, kb_id)

    response = client.post(
        f"/api/v1/sources/{source['id']}/uploads/presign",
        json={"filename": "paper.pdf", "content_type": "application/pdf"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["provider"] == "minio"
    assert data["object_key"].startswith(f"uploads/{kb_id}/{source['id']}/")
    assert data["object_key"].endswith("paper.pdf")
    assert data["upload_url"] != ""
    assert data["expires_in"] > 0
    assert data["max_size_bytes"] > 0


def test_complete_requires_auth(client: TestClient):
    """Complete endpoint should reject unauthenticated requests."""
    response = client.post(
        "/api/v1/sources/fake-id/uploads/complete",
        json={"bucket": "kb", "object_key": "uploads/kb/source/token/file.pdf"},
    )
    assert response.status_code == 401


def test_complete_source_not_found(client: TestClient, auth_headers: dict):
    """Complete for a nonexistent source should return 404."""
    response = client.post(
        "/api/v1/sources/nonexistent-id/uploads/complete",
        json={"bucket": "kb", "object_key": "uploads/kb/source/token/file.pdf"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_complete_invalid_prefix(client: TestClient, auth_headers: dict):
    """Complete should reject object_key that doesn't belong to this source."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_pending_source(client, auth_headers, kb_id)

    response = client.post(
        f"/api/v1/sources/{source['id']}/uploads/complete",
        json={
            "bucket": "knowledge_studio",
            "object_key": f"uploads/{kb_id}/OTHER_SOURCE_ID/token/file.pdf",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_complete_wrong_bucket(client: TestClient, auth_headers: dict):
    """Complete should reject a bucket that doesn't match config."""
    kb_id = _create_kb(client, auth_headers)
    source = _create_pending_source(client, auth_headers, kb_id)

    response = client.post(
        f"/api/v1/sources/{source['id']}/uploads/complete",
        json={
            "bucket": "hacker-bucket",
            "object_key": f"uploads/{kb_id}/{source['id']}/token/file.pdf",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
