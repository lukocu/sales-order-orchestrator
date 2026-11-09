from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.db import build_engine, get_engine
from app.main import app
from app.settings import BACKEND_DIR, get_settings

UNREACHABLE_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/unreachable"


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """Engine for the DATABASE_URL database after `alembic upgrade head`."""
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    engine = build_engine(get_settings().database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def unreachable_engine() -> Iterator[Engine]:
    engine = build_engine(UNREACHABLE_DATABASE_URL)
    yield engine
    engine.dispose()


def _client_with(engine: Engine) -> Iterator[TestClient]:
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(migrated_engine: Engine) -> Iterator[TestClient]:
    yield from _client_with(migrated_engine)


@pytest.fixture
def client_without_db(unreachable_engine: Engine) -> Iterator[TestClient]:
    yield from _client_with(unreachable_engine)
