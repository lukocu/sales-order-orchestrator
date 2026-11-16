from pathlib import Path

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


MAILBOX_VARIABLES = (
    "MAILBOX_PROVIDER",
    "IMAP_HOST",
    "IMAP_PORT",
    "IMAP_SSL",
    "IMAP_USERNAME",
    "IMAP_PASSWORD",
    "IMAP_FOLDER",
    "IMAP_TIMEOUT_SECONDS",
)


def test_empty_imap_password_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAP_PASSWORD", "")

    assert Settings().imap_password is None


def test_empty_mailbox_variables_mean_the_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in MAILBOX_VARIABLES:
        monkeypatch.setenv(name, "")

    settings = Settings()

    assert (settings.mailbox_provider, settings.imap_port, settings.imap_ssl) == ("fake", 993, True)
    assert (settings.imap_folder, settings.imap_timeout_seconds) == ("INBOX", 15)
    assert (settings.imap_host, settings.imap_username, settings.imap_password) == (
        None,
        None,
        None,
    )


def test_empty_mailbox_lines_of_an_env_file_mean_the_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # As copied from .env.example; real environment variables would win over the file.
    for name in MAILBOX_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("".join(f"{name}=\n" for name in MAILBOX_VARIABLES), encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert (settings.mailbox_provider, settings.imap_port, settings.imap_ssl) == ("fake", 993, True)
    assert (settings.imap_folder, settings.imap_password) == ("INBOX", None)


def test_imap_values_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAILBOX_PROVIDER", "imap")
    monkeypatch.setenv("IMAP_PORT", "3143")
    monkeypatch.setenv("IMAP_SSL", "false")
    monkeypatch.setenv("IMAP_PASSWORD", "app-password")

    settings = Settings()

    assert (settings.mailbox_provider, settings.imap_port, settings.imap_ssl) == (
        "imap",
        3143,
        False,
    )
    assert settings.imap_password is not None
    assert settings.imap_password.get_secret_value() == "app-password"
