import uuid

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _create_user() -> str:
    payload = {
        "email": f"{_uniq('user')}@example.com",
        "display_name": _uniq("User"),
        "status": "active",
    }
    resp = client.post("/api/v1/users", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    return body["data"]["id"]


def test_team_default_and_kb_exception_permissions():
    owner_user_id = _create_user()
    member_user_id = _create_user()
    outsider_user_id = _create_user()

    team_resp = client.post(
        "/api/v1/teams",
        json={"name": _uniq("team"), "creator_user_id": owner_user_id, "status": "active"},
    )
    assert team_resp.status_code == 200
    team_id = team_resp.json()["data"]["id"]

    add_member_resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": member_user_id, "role": "member"},
    )
    assert add_member_resp.status_code == 200
    assert add_member_resp.json()["data"]["role"] == "member"

    kb_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": _uniq("kb"), "owner_team_id": team_id, "owner_user_id": owner_user_id, "status": "active"},
    )
    assert kb_resp.status_code == 200
    kb_id = kb_resp.json()["data"]["id"]

    default_read = client.get(f"/api/v1/knowledge-bases/{kb_id}/permissions/{member_user_id}?action=read")
    assert default_read.status_code == 200
    default_read_body = default_read.json()["data"]
    assert default_read_body["allowed"] is True
    assert default_read_body["role"] == "viewer"
    assert default_read_body["source"] == "team_default"

    default_write = client.get(f"/api/v1/knowledge-bases/{kb_id}/permissions/{member_user_id}?action=write")
    assert default_write.status_code == 200
    assert default_write.json()["data"]["allowed"] is False

    outsider_default = client.get(f"/api/v1/knowledge-bases/{kb_id}/permissions/{outsider_user_id}?action=read")
    assert outsider_default.status_code == 200
    outsider_default_body = outsider_default.json()["data"]
    assert outsider_default_body["allowed"] is False
    assert outsider_default_body["role"] == "none"
    assert outsider_default_body["source"] == "none"

    grant_outsider = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/members",
        json={"user_id": outsider_user_id, "role": "editor"},
    )
    assert grant_outsider.status_code == 200
    assert grant_outsider.json()["data"]["role"] == "editor"

    outsider_write = client.get(f"/api/v1/knowledge-bases/{kb_id}/permissions/{outsider_user_id}?action=write")
    assert outsider_write.status_code == 200
    outsider_write_body = outsider_write.json()["data"]
    assert outsider_write_body["allowed"] is True
    assert outsider_write_body["role"] == "editor"
    assert outsider_write_body["source"] == "kb_exception"


def test_create_team_requires_existing_creator():
    resp = client.post(
        "/api/v1/teams",
        json={"name": _uniq("team"), "creator_user_id": str(uuid.uuid4()), "status": "active"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "USER_NOT_FOUND"
