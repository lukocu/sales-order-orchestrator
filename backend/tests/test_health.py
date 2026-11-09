from fastapi.testclient import TestClient


def test_health_ok_with_migrated_database(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "migration": "0001_baseline"}


def test_health_degraded_when_database_unreachable(client_without_db: TestClient) -> None:
    response = client_without_db.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "error", "migration": None}
