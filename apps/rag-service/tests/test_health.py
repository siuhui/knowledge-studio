from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_live():
    resp = client.get("/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "trace_id" in body


def test_health_ready():
    resp = client.get("/health/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "trace_id" in body
