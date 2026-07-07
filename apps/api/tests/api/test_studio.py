"""Tests for Studio report generation endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient


def _create_kb(client: TestClient, auth_headers: dict, name: str = "Test KB") -> str:
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


# ── Create task ──


def test_create_task(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.api.studio.execute_studio_task"):
        resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/studio/tasks",
            json={
                "task_type": "report",
                "title": "Security Audit Report",
                "config": {
                    "instruction": "Analyze security architecture",
                    "document_ids": None,
                    "style": "professional",
                    "length": "medium",
                },
            },
            headers=auth_headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "OK"
    assert data["data"]["task_type"] == "report"
    assert data["data"]["title"] == "Security Audit Report"
    assert data["data"]["status"] == "pending"
    assert data["data"]["progress"] == 0.0
    assert data["data"]["id"]


# ── List tasks ──


def test_list_tasks_empty(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks?page=1&page_size=20",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert data["data"] == []
    assert data["meta"]["total"] == 0


def test_list_tasks_with_items(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.api.studio.execute_studio_task"):
        for i in range(3):
            client.post(
                f"/api/v1/knowledge-bases/{kb_id}/studio/tasks",
                json={
                    "task_type": "report",
                    "title": f"Report {i}",
                    "config": {
                        "instruction": f"Topic {i}",
                        "document_ids": None,
                        "style": "professional",
                        "length": "short",
                    },
                },
                headers=auth_headers,
            )

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks?page=1&page_size=20",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 3
    assert data["meta"]["total"] == 3
    assert data["data"][0]["title"] == "Report 2"


def test_list_tasks_pagination(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.api.studio.execute_studio_task"):
        for i in range(5):
            client.post(
                f"/api/v1/knowledge-bases/{kb_id}/studio/tasks",
                json={
                    "task_type": "report",
                    "title": f"Report {i}",
                    "config": {
                        "instruction": f"Topic {i}",
                        "document_ids": None,
                        "style": "professional",
                        "length": "short",
                    },
                },
                headers=auth_headers,
            )

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks?page=1&page_size=2",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 2
    assert data["meta"]["total"] == 5
    assert data["meta"]["total_pages"] == 3


def test_list_tasks_kb_isolation(client: TestClient, auth_headers: dict):
    """Tasks from KB-A should not appear in KB-B's list."""
    kb_a = _create_kb(client, auth_headers, "KB A")
    kb_b = _create_kb(client, auth_headers, "KB B")

    with patch("app.api.studio.execute_studio_task"):
        client.post(
            f"/api/v1/knowledge-bases/{kb_a}/studio/tasks",
            json={
                "task_type": "report",
                "title": "KB A Report",
                "config": {"instruction": "Topic", "document_ids": None, "style": "professional", "length": "short"},
            },
            headers=auth_headers,
        )

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_b}/studio/tasks?page=1&page_size=20",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["data"] == []
    assert data["meta"]["total"] == 0


# ── Get task ──


def test_get_task(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.api.studio.execute_studio_task"):
        create_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/studio/tasks",
            json={
                "task_type": "report",
                "title": "Test Report",
                "config": {"instruction": "Topic", "document_ids": None, "style": "professional", "length": "short"},
            },
            headers=auth_headers,
        )
        task_id = create_resp.json()["data"]["id"]

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks/{task_id}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert data["data"]["id"] == task_id
    assert data["data"]["title"] == "Test Report"
    assert data["data"]["status"] == "pending"
    assert "config" in data["data"]
    assert data["data"]["knowledge_base_id"] == kb_id


def test_get_task_not_found(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks/nonexistent-id",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_get_task_wrong_kb(client: TestClient, auth_headers: dict):
    """Task belongs to kb_a, but we fetch it via kb_b — should 404."""
    kb_a = _create_kb(client, auth_headers, "KB A")
    kb_b = _create_kb(client, auth_headers, "KB B")

    with patch("app.api.studio.execute_studio_task"):
        create_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_a}/studio/tasks",
            json={
                "task_type": "report",
                "title": "KB A Report",
                "config": {"instruction": "Topic", "document_ids": None, "style": "professional", "length": "short"},
            },
            headers=auth_headers,
        )
        task_id = create_resp.json()["data"]["id"]

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_b}/studio/tasks/{task_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Download ──


def test_download_task_not_completed(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.api.studio.execute_studio_task"):
        create_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/studio/tasks",
            json={
                "task_type": "report",
                "title": "Test Report",
                "config": {"instruction": "Topic", "document_ids": None, "style": "professional", "length": "short"},
            },
            headers=auth_headers,
        )
        task_id = create_resp.json()["data"]["id"]

    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks/{task_id}/download",
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_download_task_not_found(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks/nonexistent-id/download",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Delete task ──


def test_delete_task(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)

    with patch("app.api.studio.execute_studio_task"):
        create_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/studio/tasks",
            json={
                "task_type": "report",
                "title": "Test Report",
                "config": {"instruction": "Topic", "document_ids": None, "style": "professional", "length": "short"},
            },
            headers=auth_headers,
        )
        task_id = create_resp.json()["data"]["id"]

    resp = client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks/{task_id}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["code"] == "OK"

    # Verify deleted
    resp = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks/{task_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_delete_task_not_found(client: TestClient, auth_headers: dict):
    kb_id = _create_kb(client, auth_headers)
    resp = client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/studio/tasks/nonexistent-id",
        headers=auth_headers,
    )
    assert resp.status_code == 404
