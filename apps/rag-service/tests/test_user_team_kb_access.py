import uuid

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AuditLog


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
        json={"operator_user_id": owner_user_id, "user_id": member_user_id, "role": "member"},
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
        json={"operator_user_id": owner_user_id, "user_id": outsider_user_id, "role": "editor"},
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


def test_permission_denied_when_non_admin_updates_team_member():
    admin_user_id = _create_user()
    normal_user_id = _create_user()
    target_user_id = _create_user()

    team_resp = client.post(
        "/api/v1/teams",
        json={"name": _uniq("team"), "creator_user_id": admin_user_id, "status": "active"},
    )
    assert team_resp.status_code == 200
    team_id = team_resp.json()["data"]["id"]

    add_member_resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"operator_user_id": admin_user_id, "user_id": normal_user_id, "role": "member"},
    )
    assert add_member_resp.status_code == 200

    denied_resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"operator_user_id": normal_user_id, "user_id": target_user_id, "role": "member"},
    )
    assert denied_resp.status_code == 403
    denied_body = denied_resp.json()
    assert denied_body["code"] == "PERMISSION_DENIED"


def test_permission_denied_when_non_owner_updates_kb_member():
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
        json={"operator_user_id": owner_user_id, "user_id": member_user_id, "role": "member"},
    )
    assert add_member_resp.status_code == 200

    kb_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": _uniq("kb"), "owner_team_id": team_id, "owner_user_id": owner_user_id, "status": "active"},
    )
    assert kb_resp.status_code == 200
    kb_id = kb_resp.json()["data"]["id"]

    denied_resp = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/members",
        json={"operator_user_id": member_user_id, "user_id": outsider_user_id, "role": "editor"},
    )
    assert denied_resp.status_code == 403
    denied_body = denied_resp.json()
    assert denied_body["code"] == "PERMISSION_DENIED"


def test_audit_log_written_for_membership_changes():
    owner_user_id = _create_user()
    member_user_id = _create_user()
    outsider_user_id = _create_user()

    team_resp = client.post(
        "/api/v1/teams",
        json={"name": _uniq("team"), "creator_user_id": owner_user_id, "status": "active"},
    )
    assert team_resp.status_code == 200
    team_id = team_resp.json()["data"]["id"]

    upsert_team_member = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"operator_user_id": owner_user_id, "user_id": member_user_id, "role": "member"},
    )
    assert upsert_team_member.status_code == 200

    kb_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": _uniq("kb"), "owner_team_id": team_id, "owner_user_id": owner_user_id, "status": "active"},
    )
    assert kb_resp.status_code == 200
    kb_id = kb_resp.json()["data"]["id"]

    upsert_kb_member = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/members",
        json={"operator_user_id": owner_user_id, "user_id": outsider_user_id, "role": "viewer"},
    )
    assert upsert_kb_member.status_code == 200

    with SessionLocal() as db:
        team_logs = db.query(AuditLog).filter(AuditLog.action == "TEAM_MEMBER_UPSERT").all()
        kb_logs = db.query(AuditLog).filter(AuditLog.action == "KNOWLEDGE_BASE_MEMBER_UPSERT").all()
        assert len(team_logs) >= 1
        assert len(kb_logs) >= 1
