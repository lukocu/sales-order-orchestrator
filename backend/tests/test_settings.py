import pytest

from app.settings import Settings

PSYCOPG_URL = "postgresql+psycopg://u:p@host:5432/db"


@pytest.mark.parametrize(
    "raw_url",
    [
        "postgresql://u:p@host:5432/db",
        "postgres://u:p@host:5432/db",
        PSYCOPG_URL,
    ],
)
def test_database_url_is_normalized_to_psycopg(raw_url: str) -> None:
    assert Settings(database_url=raw_url).database_url == PSYCOPG_URL


def test_database_url_from_environment_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")

    assert Settings().database_url == PSYCOPG_URL
