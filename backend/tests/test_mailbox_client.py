import imaplib
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import SecretStr

from app.mailbox.client import (
    DEMO_MESSAGES,
    FakeMailbox,
    MailboxAuthFailed,
    MailboxError,
    MailboxNotConfigured,
    MailboxProtocolError,
    MailboxUnavailable,
    UnconfiguredMailbox,
    get_mailbox,
)
from app.mailbox.imap import ImapMailbox
from app.mailbox.message import MailCandidate, to_candidate
from app.settings import Settings

SERVER_TEXT = "server-said-something-private"
IMAP_ERROR = imaplib.IMAP4.error
IMAP_ABORT = imaplib.IMAP4.abort


@dataclass
class Server:
    """Scripted IMAP server; `connect` stands in for `imaplib.IMAP4_SSL` / `IMAP4`."""

    uids: list[int] = field(default_factory=list)
    connect_error: BaseException | None = None
    login_error: BaseException | None = None
    select_status: str = "OK"
    search_status: str = "OK"
    fetch_error: BaseException | None = None
    logout_error: BaseException | None = None
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def connect(self, host: str, port: int, *, timeout: float | None = None) -> Connection:
        self.calls.append(("connect", host, port, timeout))
        if self.connect_error is not None:
            raise self.connect_error
        return Connection(self)

    def names(self) -> list[str]:
        return [call[0] for call in self.calls]


def raw_message(uid: int) -> bytes:
    return f"Message-ID: <{uid}@test>\r\n\r\nbody {uid}\r\n".encode()


class Connection:
    def __init__(self, server: Server) -> None:
        self._server = server

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        self._server.calls.append(("login", user, password))
        if self._server.login_error is not None:
            raise self._server.login_error
        return "OK", [b"logged in"]

    def select(self, mailbox: str = "INBOX", readonly: bool = False) -> tuple[str, list[bytes]]:
        self._server.calls.append(("select", mailbox, readonly))
        return self._server.select_status, [str(len(self._server.uids)).encode()]

    def uid(self, command: str, *args: str) -> tuple[str, list[Any]]:
        self._server.calls.append(("uid", command, *args))
        if command == "SEARCH":
            return self._server.search_status, [" ".join(map(str, self._server.uids)).encode()]
        assert command == "FETCH"
        if self._server.fetch_error is not None:
            raise self._server.fetch_error
        wanted = {int(uid) for uid in args[0].split(",")}
        data: list[Any] = []
        for sequence, uid in enumerate(self._server.uids, start=1):
            if uid in wanted:
                raw = raw_message(uid)
                data.append((f"{sequence} (UID {uid} BODY[] {{{len(raw)}}}".encode(), raw))
                data.append(b")")
        return "OK", data

    def logout(self) -> tuple[str, list[bytes]]:
        self._server.calls.append(("logout",))
        if self._server.logout_error is not None:
            raise self._server.logout_error
        return "BYE", [b"bye"]


def _mailbox(*, ssl_on: bool = True) -> ImapMailbox:
    return ImapMailbox(
        host="imap.test",
        port=993,
        ssl=ssl_on,
        username="reader",
        password="app-password",
        folder="INBOX",
        timeout_seconds=7,
    )


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Server:
    scripted = Server()
    monkeypatch.setattr(imaplib, "IMAP4_SSL", scripted.connect)
    monkeypatch.setattr(imaplib, "IMAP4", scripted.connect)
    return scripted


def _assert_constant(error: MailboxError, message: str) -> None:
    assert str(error) == message
    assert SERVER_TEXT not in str(error)
    assert error.__cause__ is None
    # Raised `from None` (or with nothing to chain): the original error is not shown.
    assert error.__suppress_context__ or error.__context__ is None


def test_reads_only_the_newest_uids_read_only_and_newest_first(server: Server) -> None:
    server.uids = [3, 5, 8, 13, 21]

    messages = _mailbox().latest(3)

    assert messages == [raw_message(21), raw_message(13), raw_message(8)]
    assert server.calls == [
        ("connect", "imap.test", 993, 7),
        ("login", "reader", "app-password"),
        ("select", "INBOX", True),
        ("uid", "SEARCH", "ALL"),
        ("uid", "FETCH", "8,13,21", "(BODY.PEEK[])"),
        ("logout",),
    ]


def test_fewer_messages_than_the_limit_are_all_read(server: Server) -> None:
    server.uids = [1, 2]

    assert _mailbox().latest(20) == [raw_message(2), raw_message(1)]


def test_empty_folder_fetches_nothing(server: Server) -> None:
    assert _mailbox().latest(20) == []
    assert server.names() == ["connect", "login", "select", "uid", "logout"]


def test_plain_imap_without_tls_uses_imap4(server: Server, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_tls(*args: object, **kwargs: object) -> None:
        raise AssertionError("IMAP4_SSL used with ssl=False")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", no_tls)
    server.uids = [1]

    assert _mailbox(ssl_on=False).latest(5) == [raw_message(1)]


def test_rejected_login_is_auth_failed(server: Server) -> None:
    server.login_error = IMAP_ERROR(f"[AUTHENTICATIONFAILED] {SERVER_TEXT}")

    with pytest.raises(MailboxAuthFailed) as raised:
        _mailbox().latest(20)

    _assert_constant(raised.value, "Mailbox login failed")
    assert server.names() == ["connect", "login", "logout"]


@pytest.mark.parametrize(
    "error",
    [
        ConnectionRefusedError(SERVER_TEXT),
        TimeoutError(SERVER_TEXT),
        ssl.SSLError(SERVER_TEXT),
        OSError(SERVER_TEXT),
    ],
)
def test_network_timeout_and_tls_errors_are_unavailable(
    server: Server, error: BaseException
) -> None:
    server.connect_error = error

    with pytest.raises(MailboxUnavailable) as raised:
        _mailbox().latest(20)

    _assert_constant(raised.value, "Mailbox unavailable")


def test_broken_connection_is_unavailable(server: Server) -> None:
    server.uids = [1]
    server.fetch_error = IMAP_ABORT(f"socket error: {SERVER_TEXT}")

    with pytest.raises(MailboxUnavailable) as raised:
        _mailbox().latest(20)

    _assert_constant(raised.value, "Mailbox unavailable")
    assert server.names()[-1] == "logout"


def test_timeout_during_fetch_is_unavailable(server: Server) -> None:
    server.uids = [1]
    server.fetch_error = TimeoutError(SERVER_TEXT)

    with pytest.raises(MailboxUnavailable):
        _mailbox().latest(20)


def test_imap_error_after_login_is_a_protocol_error(server: Server) -> None:
    server.uids = [1]
    server.fetch_error = IMAP_ERROR(f"UID command error: BAD [{SERVER_TEXT}]")

    with pytest.raises(MailboxProtocolError) as raised:
        _mailbox().latest(20)

    _assert_constant(raised.value, "Mailbox error")
    assert server.names()[-1] == "logout"


@pytest.mark.parametrize("failing", ["select_status", "search_status"])
def test_answer_other_than_ok_is_a_protocol_error(server: Server, failing: str) -> None:
    server.uids = [1]
    setattr(server, failing, "NO")

    with pytest.raises(MailboxProtocolError) as raised:
        _mailbox().latest(20)

    _assert_constant(raised.value, "Mailbox error")
    assert "FETCH" not in [call[1] for call in server.calls if call[0] == "uid"]


@pytest.mark.parametrize("error", [IMAP_ERROR(SERVER_TEXT), OSError(SERVER_TEXT)])
def test_failing_logout_keeps_the_result(server: Server, error: BaseException) -> None:
    server.uids = [1]
    server.logout_error = error

    assert _mailbox().latest(20) == [raw_message(1)]


def test_non_positive_limit_does_not_connect(server: Server) -> None:
    assert _mailbox().latest(0) == []
    assert server.calls == []


def test_fake_mailbox_returns_the_last_messages_newest_first() -> None:
    mailbox = FakeMailbox([b"1", b"2", b"3"])

    assert mailbox.latest(2) == [b"3", b"2"]
    assert mailbox.latest(10) == [b"3", b"2", b"1"]
    assert mailbox.latest(0) == []


def test_demo_messages_convert_to_polish_inquiries_from_example_senders() -> None:
    fetched_at = datetime(2026, 11, 15, tzinfo=UTC)
    candidates = [to_candidate(raw, fetched_at=fetched_at) for raw in DEMO_MESSAGES]

    assert len(candidates) == 2
    assert all(isinstance(c, MailCandidate) for c in candidates)
    assert all(
        isinstance(c, MailCandidate) and c.sender_email.endswith(".example") for c in candidates
    )
    assert len({c.external_id for c in candidates if isinstance(c, MailCandidate)}) == 2


def test_unconfigured_mailbox_raises_not_configured() -> None:
    with pytest.raises(MailboxNotConfigured):
        UnconfiguredMailbox().latest(20)


def _settings(**values: Any) -> Settings:
    return Settings(**values)


def test_factory_returns_the_fake_by_default() -> None:
    assert isinstance(get_mailbox(_settings(mailbox_provider="fake")), FakeMailbox)


@pytest.mark.parametrize("missing", ["imap_host", "imap_username", "imap_password"])
def test_factory_without_credentials_is_unconfigured(missing: str) -> None:
    values: dict[str, Any] = {
        "mailbox_provider": "imap",
        "imap_host": "imap.test",
        "imap_username": "reader",
        "imap_password": SecretStr("app-password"),
    }
    values[missing] = None

    assert isinstance(get_mailbox(_settings(**values)), UnconfiguredMailbox)


def test_factory_with_credentials_returns_the_imap_client(server: Server) -> None:
    mailbox = get_mailbox(
        _settings(
            mailbox_provider="imap",
            imap_host="imap.test",
            imap_port=3143,
            imap_ssl=False,
            imap_username="reader",
            imap_password=SecretStr("app-password"),
            imap_folder="Zapytania",
            imap_timeout_seconds=4,
        )
    )
    assert isinstance(mailbox, ImapMailbox)

    mailbox.latest(1)

    assert server.calls[:3] == [
        ("connect", "imap.test", 3143, 4),
        ("login", "reader", "app-password"),
        ("select", "Zapytania", True),
    ]
