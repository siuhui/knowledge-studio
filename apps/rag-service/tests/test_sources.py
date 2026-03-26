from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_source_and_list_sources():
    payload = {
        "name": "test-source",
        "source_type": "local",
        "sync_mode": "scheduled",
        "status": "active",
        "config_json": "{}",
    }

    create_resp = client.post("/api/v1/sources", json=payload)
    assert create_resp.status_code == 200
    create_body = create_resp.json()
    assert create_body["code"] == "OK"
    assert create_body["data"]["name"] == "test-source"

    list_resp = client.get("/api/v1/sources")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["code"] == "OK"
    assert isinstance(list_body["data"]["items"], list)


def test_create_source_validation_error():
    create_resp = client.post("/api/v1/sources", json={"source_type": "local"})
    assert create_resp.status_code == 422
    body = create_resp.json()
    assert body["code"] == "VALIDATION_ERROR"
