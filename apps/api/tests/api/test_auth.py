from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "OK"
    assert data["data"]["username"] == "alice"


def test_register_duplicate_username(client: TestClient):
    client.post("/api/v1/auth/register", json={"username": "bob", "password": "password123"})
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "password": "password456"},
    )
    assert response.status_code == 409


def test_login_success(client: TestClient):
    client.post("/api/v1/auth/register", json={"username": "carol", "password": "password123"})
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "carol", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "OK"
    assert "access_token" in data["data"]


def test_login_invalid_credentials(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert response.status_code == 401
