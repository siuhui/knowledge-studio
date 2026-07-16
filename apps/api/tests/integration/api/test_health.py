from fastapi.testclient import TestClient


def test_health_live(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready(client: TestClient):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
