from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from app.settings import BACKEND_DIR


def test_health_ok_with_migrated_database(client: TestClient) -> None:
    head = ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_current_head()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "migration": head}


def test_health_degraded_when_database_unreachable(client_without_db: TestClient) -> None:
    response = client_without_db.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "error", "migration": None}
