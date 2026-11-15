import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.auth.models import Role
from app.mailbox.client import (
    FakeMailbox,
    MailboxAuthFailed,
    MailboxError,
    MailboxProtocolError,
    MailboxUnavailable,
    UnconfiguredMailbox,
)
from app.mailbox.service import MAILBOX_LOCK_KEY
from tests.conftest import TEST_EMAIL_DOMAIN, TEST_PASSWORD, MailboxSetter, UserFactory
from tests.test_mailbox_service import make_mail

PATH = "/api/mailbox/fetch"
SERVER_TEXT = "server-said-something-private"


class FailingMailbox:
    name = "imap"

    def __init__(self, error: MailboxError) -> None:
        self._error = error

    def latest(self, limit: int) -> list[bytes]:
        raise self._error


def test_without_session_is_401(client: TestClient, use_mailbox: MailboxSetter) -> None:
    use_mailbox(FakeMailbox([make_mail()]))

    response = client.post(PATH)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.parametrize("role", ["salesperson", "supervisor"])
def test_any_signed_in_user_fetches_and_a_second_fetch_finds_duplicates(
    client: TestClient, make_user: UserFactory, use_mailbox: MailboxSetter, role: Role
) -> None:
    user = make_user(role=role, password=TEST_PASSWORD)
    login = client.post(
        "/api/auth/login", json={"username": user.username, "password": TEST_PASSWORD}
    )
    assert login.status_code == 200
    use_mailbox(FakeMailbox([make_mail(), make_mail()]))

    first = client.post(PATH)
    second = client.post(PATH)

    assert first.status_code == 200
    assert first.json() == {"fetched": 2, "created": 2, "duplicates": 0, "skipped": 0}
    assert second.status_code == 200
    assert second.json() == {"fetched": 2, "created": 0, "duplicates": 2, "skipped": 0}


def test_fetched_mail_is_listed_with_its_source(
    auth_client: TestClient, use_mailbox: MailboxSetter
) -> None:
    use_mailbox(FakeMailbox([make_mail()]))
    assert auth_client.post(PATH).status_code == 200

    rows = [
        r
        for r in auth_client.get("/api/inquiries").json()
        if r["sender_email"].endswith(f"@{TEST_EMAIL_DOMAIN}")
    ]

    assert [r["source"] for r in rows] == ["mailbox"]
    assert "external_id" not in rows[0]
    detail = auth_client.get(f"/api/inquiries/{rows[0]['id']}").json()
    assert detail["source"] == "mailbox"
    assert "external_id" not in detail


def test_unconfigured_mailbox_is_503(auth_client: TestClient, use_mailbox: MailboxSetter) -> None:
    use_mailbox(UnconfiguredMailbox())

    response = auth_client.post(PATH)

    assert response.status_code == 503
    assert response.json() == {"detail": "Mailbox not configured"}


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (MailboxAuthFailed(SERVER_TEXT), "Mailbox login failed"),
        (MailboxUnavailable(SERVER_TEXT), "Mailbox unavailable"),
        (MailboxProtocolError(SERVER_TEXT), "Mailbox error"),
    ],
)
def test_mailbox_errors_are_502_without_server_text(
    auth_client: TestClient,
    use_mailbox: MailboxSetter,
    caplog: pytest.LogCaptureFixture,
    error: MailboxError,
    detail: str,
) -> None:
    use_mailbox(FailingMailbox(error))

    with caplog.at_level(logging.INFO):
        response = auth_client.post(PATH)

    assert response.status_code == 502
    assert response.json() == {"detail": detail}
    assert SERVER_TEXT not in caplog.text
    assert type(error).__name__ in caplog.text


def test_fetch_in_progress_is_409(
    auth_client: TestClient, use_mailbox: MailboxSetter, migrated_engine: Engine
) -> None:
    use_mailbox(FakeMailbox([make_mail()]))
    with migrated_engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MAILBOX_LOCK_KEY})
        try:
            response = auth_client.post(PATH)
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MAILBOX_LOCK_KEY})

    assert response.status_code == 409
    assert response.json() == {"detail": "Mailbox fetch already in progress"}


def test_unreachable_database_is_json_503(client_without_db: TestClient) -> None:
    # Any cookie: without one the 401 comes before the database is touched.
    client_without_db.cookies.set("session", "any-token")

    response = client_without_db.post(PATH)

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
