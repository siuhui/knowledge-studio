import uuid

from fastapi.testclient import TestClient

import app.services.uploads_service as uploads_service
from app.main import app


client = TestClient(app)


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _create_user() -> str:
    resp = client.post(
        "/api/v1/users",
        json={
            "email": f"{_uniq('user')}@example.com",
            "display_name": _uniq("User"),
            "status": "active",
        },
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


def _create_kb() -> tuple[str, str]:
    owner_user_id = _create_user()
    team_resp = client.post(
        "/api/v1/teams",
        json={"name": _uniq("team"), "creator_user_id": owner_user_id, "status": "active"},
    )
    assert team_resp.status_code == 200
    team_id = team_resp.json()["data"]["id"]
    kb_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": _uniq("kb"), "owner_team_id": team_id, "owner_user_id": owner_user_id, "status": "active"},
    )
    assert kb_resp.status_code == 200
    return kb_resp.json()["data"]["id"], owner_user_id


def test_create_upload_presign_success(monkeypatch):
    kb_id, owner_user_id = _create_kb()
    monkeypatch.setattr(
        uploads_service,
        "_build_presigned_post",
        lambda object_key, content_type, original_filename: (
            "https://example.com/upload",
            {
                "key": object_key,
                "Content-Type": content_type,
                "x-amz-meta-original-filename": original_filename,
            },
        ),
    )

    resp = client.post(
        "/api/v1/uploads/presign",
        json={
            "user_id": owner_user_id,
            "kb_id": kb_id,
            "filename": "handbook.pdf",
            "content_type": "application/pdf",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    assert body["data"]["bucket"]
    assert body["data"]["object_key"].startswith(f"kb/{kb_id}/")
    assert body["data"]["upload_method"] == "POST"
    assert body["data"]["upload_url"] == "https://example.com/upload"
    assert "upload_fields" in body["data"]
    assert body["data"]["max_size_bytes"] > 0


def test_complete_upload_success(monkeypatch):
    kb_id, owner_user_id = _create_kb()
    monkeypatch.setattr(
        uploads_service,
        "_head_object",
        lambda bucket, object_key: {
            "ContentLength": 128,
            "ContentType": "text/plain",
            "ETag": '"abc"',
            "Metadata": {"original-filename": "hello.txt"},
        },
    )
    resp = client.post(
        "/api/v1/uploads/complete",
        json={
            "kb_id": kb_id,
            "bucket": "kb-source",
            "object_key": f"kb/{kb_id}/kb/raw/20260402/xx-file.txt",
            "etag": "abc",
            "uploader_user_id": owner_user_id,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    assert body["data"]["accepted"] is True
    assert body["data"]["uploaded_object_id"]


def test_list_get_delete_uploads(monkeypatch):
    kb_id, owner_user_id = _create_kb()
    monkeypatch.setattr(
        uploads_service,
        "_head_object",
        lambda bucket, object_key: {
            "ContentLength": 321,
            "ContentType": "text/plain",
            "ETag": '"etag-1"',
            "Metadata": {"original-filename": "notes.txt"},
        },
    )
    monkeypatch.setattr(uploads_service, "_delete_object", lambda bucket, object_key: None)

    complete = client.post(
        "/api/v1/uploads/complete",
        json={
            "kb_id": kb_id,
            "bucket": "kb-source",
            "object_key": f"kb/{kb_id}/kb/raw/20260402/xx-file.txt",
            "uploader_user_id": owner_user_id,
        },
    )
    assert complete.status_code == 200
    uploaded_id = complete.json()["data"]["uploaded_object_id"]

    list_resp = client.get(f"/api/v1/uploads?kb_id={kb_id}&user_id={owner_user_id}&page=1&page_size=20")
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert any(item["id"] == uploaded_id for item in items)

    detail_resp = client.get(f"/api/v1/uploads/{uploaded_id}?user_id={owner_user_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["data"]["status"] == "uploaded"

    delete_resp = client.delete(f"/api/v1/uploads/{uploaded_id}?user_id={owner_user_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["accepted"] is True

    list_resp_after = client.get(f"/api/v1/uploads?kb_id={kb_id}&user_id={owner_user_id}&page=1&page_size=20")
    assert list_resp_after.status_code == 200
    assert all(item["id"] != uploaded_id for item in list_resp_after.json()["data"]["items"])
