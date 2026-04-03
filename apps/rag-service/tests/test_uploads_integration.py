import urllib.request
import uuid

import boto3
import pytest
from botocore.config import Config
from fastapi.testclient import TestClient

from app.config import settings
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
    kb_name = _uniq("kb")
    kb_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name, "owner_team_id": team_id, "owner_user_id": owner_user_id, "status": "active"},
    )
    assert kb_resp.status_code == 200
    kb_id = kb_resp.json()["data"]["id"]
    return kb_id, owner_user_id


def _minio_healthcheck() -> bool:
    try:
        with urllib.request.urlopen(f"{settings.object_storage_endpoint}/minio/health/live", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.mark.integration
def test_upload_presign_and_complete_with_minio():
    if not _minio_healthcheck():
        pytest.skip("minio is not reachable")

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
        config=Config(s3={"addressing_style": "path"}),
    )
    bucket = settings.object_storage_bucket
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)

    kb_id, owner_user_id = _create_kb()
    filename = f"it-{uuid.uuid4().hex}.txt"
    presign_resp = client.post(
        "/api/v1/uploads/presign",
        json={"user_id": owner_user_id, "kb_id": kb_id, "filename": filename, "content_type": "text/plain"},
    )
    assert presign_resp.status_code == 200
    data = presign_resp.json()["data"]
    assert data["bucket"] == bucket
    assert data["object_key"].startswith(f"kb/{kb_id}/")
    assert "/raw/" in data["object_key"]
    assert data["upload_method"] == "POST"
    assert data["upload_url"]
    assert data["upload_fields"]

    body, multipart_ct = _encode_multipart_form(
        data["upload_fields"],
        "file",
        filename,
        b"integration upload content",
        "text/plain",
    )
    req = urllib.request.Request(data["upload_url"], data=body, method="POST", headers={"Content-Type": multipart_ct})
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status in (200, 204)

    s3.head_object(Bucket=bucket, Key=data["object_key"])

    complete_resp = client.post(
        "/api/v1/uploads/complete",
        json={
            "kb_id": kb_id,
            "bucket": bucket,
            "object_key": data["object_key"],
            "etag": "integration-etag",
        },
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["data"]["accepted"] is True
def _encode_multipart_form(fields: dict[str, str], file_field: str, filename: str, content: bytes, content_type: str):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for key, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        lines.append(f"{value}\r\n".encode())
    lines.append(f"--{boundary}\r\n".encode())
    lines.append(f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode())
    lines.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    lines.append(content)
    lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode())
    body = b"".join(lines)
    return body, f"multipart/form-data; boundary={boundary}"

