import uuid

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource


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


def _seed_kb_content(kb_id: str, text: str) -> None:
    with SessionLocal() as db:
        source = KnowledgeSource(
            id=str(uuid.uuid4()),
            name=_uniq("source"),
            source_type="local",
            sync_mode="manual",
            status="active",
            config_json="{}",
        )
        db.add(source)
        db.flush()

        doc = KnowledgeDocument(
            id=str(uuid.uuid4()),
            source_id=source.id,
            title=_uniq("doc"),
            path="/tmp/mock.md",
            doc_version="1",
            department=None,
            permission_scope=kb_id,
            status="active",
        )
        db.add(doc)
        db.flush()

        chunk = KnowledgeChunk(
            id=str(uuid.uuid4()),
            doc_id=doc.id,
            chunk_index=0,
            content=text,
            token_count=max(len(text.split()), 1),
            index_version="1",
            permission_scope=kb_id,
        )
        db.add(chunk)
        db.commit()


def _setup_kb() -> tuple[str, str, str]:
    owner_user_id = _create_user()
    member_user_id = _create_user()
    outsider_user_id = _create_user()

    team_resp = client.post(
        "/api/v1/teams",
        json={"name": _uniq("team"), "creator_user_id": owner_user_id, "status": "active"},
    )
    assert team_resp.status_code == 200
    team_id = team_resp.json()["data"]["id"]

    member_resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"operator_user_id": owner_user_id, "user_id": member_user_id, "role": "member"},
    )
    assert member_resp.status_code == 200

    kb_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": _uniq("kb"), "owner_team_id": team_id, "owner_user_id": owner_user_id, "status": "active"},
    )
    assert kb_resp.status_code == 200
    kb_id = kb_resp.json()["data"]["id"]
    return kb_id, member_user_id, outsider_user_id


def test_retrieval_query_returns_ranked_items_for_authorized_user():
    kb_id, member_user_id, _ = _setup_kb()
    _seed_kb_content(kb_id, "RAG retrieval pipeline supports chunk ranking and citations.")

    resp = client.post(
        "/api/v1/retrieval/query",
        json={"kb_id": kb_id, "user_id": member_user_id, "query": "chunk ranking", "top_k": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    assert len(body["data"]["items"]) >= 1
    assert body["data"]["items"][0]["score"] > 0


def test_qa_ask_returns_grounded_answer_with_citations():
    kb_id, member_user_id, _ = _setup_kb()
    _seed_kb_content(kb_id, "Knowledge base answers should include citations for trust.")

    resp = client.post(
        "/api/v1/qa/ask",
        json={"kb_id": kb_id, "user_id": member_user_id, "question": "citations", "top_k": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    assert body["data"]["grounded"] is True
    assert len(body["data"]["citations"]) >= 1


def test_retrieval_query_denied_for_unauthorized_user():
    kb_id, _, outsider_user_id = _setup_kb()
    _seed_kb_content(kb_id, "Unauthorized users should not read private team knowledge.")

    resp = client.post(
        "/api/v1/retrieval/query",
        json={"kb_id": kb_id, "user_id": outsider_user_id, "query": "private knowledge", "top_k": 5},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["code"] == "PERMISSION_DENIED"
