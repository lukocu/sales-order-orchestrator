import imaplib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import SecretStr

from app.mailbox import demo
from app.mailbox.message import MailCandidate, to_candidate
from app.settings import Settings

SERVER_TEXT = "server-said-something-private"
IMAP_ERROR = imaplib.IMAP4.error
PASSWORD = "demo-secret"

LOCAL = {
    "mailbox_provider": "imap",
    "imap_host": "mail",
    "imap_port": 3143,
    "imap_ssl": False,
    "imap_username": "sales",
    "imap_password": SecretStr(PASSWORD),
    "imap_folder": "INBOX",
}


@dataclass
class Server:
    """Stands in for `imaplib.IMAP4` / `IMAP4_SSL`; records every call, no network."""

    login_error: BaseException | None = None
    connect_error: BaseException | None = None
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def connect(self, host: str, port: int, *, timeout: float | None = None) -> Connection:
        self.calls.append(("connect", host, port))
        if self.connect_error is not None:
            raise self.connect_error
        return Connection(self)

    def names(self) -> list[str]:
        return [call[0] for call in self.calls]


class Connection:
    def __init__(self, server: Server) -> None:
        self._server = server

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        self._server.calls.append(("login", user, password))
        if self._server.login_error is not None:
            raise self._server.login_error
        return "OK", [b"logged in"]

    def append(
        self, mailbox: str, flags: str | None, date_time: Any, message: bytes
    ) -> tuple[str, list[bytes]]:
        self._server.calls.append(("append", mailbox, message))
        return "OK", [b"appended"]

    def logout(self) -> tuple[str, list[bytes]]:
        self._server.calls.append(("logout",))
        return "BYE", [b"bye"]


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Server:
    scripted = Server()
    monkeypatch.setattr(imaplib, "IMAP4", scripted.connect)
    monkeypatch.setattr(imaplib, "IMAP4_SSL", scripted.connect)
    return scripted


def _use_settings(monkeypatch: pytest.MonkeyPatch, **update: Any) -> None:
    settings = Settings().model_copy(update={**LOCAL, **update})
    monkeypatch.setattr(demo, "get_settings", lambda: settings)


@pytest.mark.parametrize(
    "update",
    [
        {"mailbox_provider": "fake"},
        {"imap_ssl": True},
        {"imap_host": "imap.gmail.com"},
        {"imap_host": None},
        {"imap_username": None},
        {"imap_password": None},
    ],
    ids=["fake", "ssl", "gmail-host", "no-host", "no-username", "no-password"],
)
def test_main_refuses_anything_but_the_local_mailbox(
    monkeypatch: pytest.MonkeyPatch,
    server: Server,
    capsys: pytest.CaptureFixture[str],
    update: dict[str, Any],
) -> None:
    _use_settings(monkeypatch, **update)

    assert demo.main() == 2
    assert server.calls == []
    assert "Refusing" in capsys.readouterr().err


@pytest.mark.parametrize("host", sorted(demo.LOCAL_HOSTS))
def test_main_appends_the_sample_mails_to_the_folder(
    monkeypatch: pytest.MonkeyPatch,
    server: Server,
    capsys: pytest.CaptureFixture[str],
    host: str,
) -> None:
    _use_settings(monkeypatch, imap_host=host, imap_folder="Demo")

    assert demo.main() == 0

    assert server.names() == ["connect", "login", "append", "append", "append", "logout"]
    assert server.calls[0] == ("connect", host, 3143)
    assert server.calls[1] == ("login", "sales", PASSWORD)
    appends = [call for call in server.calls if call[0] == "append"]
    assert [call[1] for call in appends] == ["Demo"] * 3
    assert [call[2] for call in appends] == list(demo.DEMO_MAILS)
    output = capsys.readouterr()
    assert "Appended 3 of 3" in output.out
    assert PASSWORD not in output.out + output.err


@pytest.mark.parametrize(
    "error_field",
    ["login_error", "connect_error"],
)
def test_main_fails_without_quoting_the_server(
    monkeypatch: pytest.MonkeyPatch,
    server: Server,
    capsys: pytest.CaptureFixture[str],
    error_field: str,
) -> None:
    error: BaseException = (
        IMAP_ERROR(SERVER_TEXT)
        if error_field == "login_error"
        else ConnectionRefusedError(SERVER_TEXT)
    )
    setattr(server, error_field, error)
    _use_settings(monkeypatch)

    assert demo.main() == 1

    output = capsys.readouterr()
    assert SERVER_TEXT not in output.out + output.err
    assert PASSWORD not in output.out + output.err
    if error_field == "login_error":
        assert server.names()[-1] == "logout"


def _candidates() -> list[MailCandidate]:
    fetched_at = datetime(2026, 11, 15, tzinfo=UTC)
    candidates = [to_candidate(raw, fetched_at=fetched_at) for raw in demo.DEMO_MAILS]
    assert all(isinstance(candidate, MailCandidate) for candidate in candidates)
    return [candidate for candidate in candidates if isinstance(candidate, MailCandidate)]


def test_sample_mails_have_distinct_fixed_ids_and_example_senders() -> None:
    candidates = _candidates()

    assert len({candidate.external_id for candidate in candidates}) == 3
    assert all(candidate.sender_email.endswith(".example") for candidate in candidates)
    assert [candidate.external_id for candidate in _candidates()] == [
        candidate.external_id for candidate in candidates
    ]


def test_sample_mails_convert_to_clean_bodies_ending_with_the_signature() -> None:
    plain, html, reply = _candidates()

    assert plain.body.endswith("Hurtownia Delta")
    assert html.body.endswith("Zaopatrzenie, Technika Omega")
    assert "<" not in html.body
    assert "margin" not in html.body
    assert reply.body.endswith("Dział zakupów, ACME Sp. z o.o.")
    assert "napisał" not in reply.body
    assert ">" not in reply.body
