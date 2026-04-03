import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.services.uploads_service as uploads_service
from app.database import Base, engine
from app.main import app
from app.models import UploadedObject, UploadedObjectStatus


Base.metadata.create_all(bind=engine)
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
    kb_id = kb_resp.json()["data"]["id"]
    return kb_id, owner_user_id


def test_local_ingest_chunk_index_pipeline_success(tmp_path: Path):
    kb_id, owner_user_id = _create_kb()
    (tmp_path / "a.txt").write_text("RAG indexing pipeline builds chunks for retrieval.", encoding="utf-8")

    source_resp = client.post(
        "/api/v1/sources",
        json={
            "name": _uniq("source"),
            "source_type": "local",
            "sync_mode": "manual",
            "status": "active",
            "config_json": json.dumps({"base_path": str(tmp_path), "kb_id": kb_id}),
        },
    )
    assert source_resp.status_code == 200
    source_id = source_resp.json()["data"]["id"]

    job_resp = client.post("/api/v1/index/jobs", json={"source_id": source_id, "mode": "incremental"})
    assert job_resp.status_code == 200
    assert job_resp.json()["data"]["status"] == "success"
    job_id = job_resp.json()["data"]["job_id"]

    detail_resp = client.get(f"/api/v1/index/jobs/{job_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["status"] == "success"
    assert detail["total_documents"] == 1
    assert detail["indexed_documents"] == 1

    retrieval_resp = client.post(
        "/api/v1/retrieval/query",
        json={"kb_id": kb_id, "user_id": owner_user_id, "query": "chunks retrieval", "top_k": 5},
    )
    assert retrieval_resp.status_code == 200
    assert len(retrieval_resp.json()["data"]["items"]) >= 1


def test_create_index_job_rejects_non_active_source(tmp_path: Path):
    kb_id, _ = _create_kb()
    source_resp = client.post(
        "/api/v1/sources",
        json={
            "name": _uniq("source"),
            "source_type": "local",
            "sync_mode": "manual",
            "status": "paused",
            "config_json": json.dumps({"base_path": str(tmp_path), "kb_id": kb_id}),
        },
    )
    assert source_resp.status_code == 200
    source_id = source_resp.json()["data"]["id"]

    job_resp = client.post("/api/v1/index/jobs", json={"source_id": source_id, "mode": "incremental"})
    assert job_resp.status_code == 400
    assert job_resp.json()["code"] == "SOURCE_NOT_ACTIVE"


def test_index_job_updates_uploaded_object_status(tmp_path: Path, monkeypatch):
    kb_id, owner_user_id = _create_kb()
    (tmp_path / "b.txt").write_text("Indexing should flip uploaded objects to indexed.", encoding="utf-8")

    monkeypatch.setattr(
        uploads_service,
        "_head_object",
        lambda bucket, object_key: {
            "ContentLength": 128,
            "ContentType": "text/plain",
            "ETag": '"e1"',
            "Metadata": {"original-filename": "b.txt"},
        },
    )

    complete_resp = client.post(
        "/api/v1/uploads/complete",
        json={
            "kb_id": kb_id,
            "bucket": "kb-source",
            "object_key": f"kb/{kb_id}/kb/raw/20260403/sample.txt",
            "uploader_user_id": owner_user_id,
        },
    )
    assert complete_resp.status_code == 200
    uploaded_id = complete_resp.json()["data"]["uploaded_object_id"]

    source_resp = client.post(
        "/api/v1/sources",
        json={
            "name": _uniq("source"),
            "source_type": "local",
            "sync_mode": "manual",
            "status": "active",
            "config_json": json.dumps({"base_path": str(tmp_path), "kb_id": kb_id}),
        },
    )
    assert source_resp.status_code == 200
    source_id = source_resp.json()["data"]["id"]

    job_resp = client.post("/api/v1/index/jobs", json={"source_id": source_id, "mode": "incremental"})
    assert job_resp.status_code == 200
    assert job_resp.json()["data"]["status"] == "success"

    from app.database import SessionLocal

    with SessionLocal() as db:
        row = db.scalar(select(UploadedObject).where(UploadedObject.id == uploaded_id))
        assert row is not None
        assert row.status == UploadedObjectStatus.indexed
