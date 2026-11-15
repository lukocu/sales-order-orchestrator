"""Mailbox interface, its errors and the choice of implementation from settings.

Error messages are constant: they never carry server responses, credentials or message
content, so they are safe to log and to show.
"""

from collections.abc import Sequence
from email.message import EmailMessage
from typing import Annotated, Protocol

from fastapi import Depends

from app.settings import Settings, get_settings


class MailboxError(Exception):
    """The mailbox could not be read."""


class MailboxNotConfigured(MailboxError):
    """`imap` is selected but the host, username or password is not set."""


class MailboxAuthFailed(MailboxError):
    """The server rejected the login."""


class MailboxUnavailable(MailboxError):
    """Network error, timeout or TLS failure."""


class MailboxProtocolError(MailboxError):
    """The server answered something unexpected."""


class Mailbox(Protocol):
    name: str  # fake, imap

    def latest(self, limit: int) -> list[bytes]:
        """Raw RFC 5322 bytes of at most `limit` newest messages, newest (highest UID)
        first."""
        ...


def _demo_message(*, message_id: str, date: str, sender: str, subject: str, body: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "sprzedaz@firma.example"
    msg["Subject"] = subject
    msg["Date"] = date
    msg["Message-ID"] = message_id
    msg.set_content(body)
    return msg.as_bytes()


# Oldest first, like ascending UIDs. Fictional companies and the reserved .example domain
# (RFC 2606); fixed Message-IDs, so a second fetch finds them already stored.
DEMO_MESSAGES: tuple[bytes, ...] = (
    _demo_message(
        message_id="<demo-1@acme.example>",
        date="Fri, 13 Nov 2026 09:20:00 +0100",
        sender="Marek Nowak <zakupy@acme.example>",
        subject="Zapytanie: 40 szt. ABC-200",
        body=(
            "Dzień dobry,\n\n"
            "prosimy o ofertę na 40 szt. ABC-200 z dostawą do środy. "
            "Możemy przyjąć podobny model o zbliżonych parametrach.\n\n"
            "Prosimy o najlepszą cenę.\n\n"
            "Pozdrawiam,\n"
            "Marek Nowak\n"
            "Dział zakupów, ACME Sp. z o.o."
        ),
    ),
    _demo_message(
        message_id="<demo-2@biuromax.example>",
        date="Fri, 13 Nov 2026 11:45:00 +0100",
        sender="Katarzyna Zielińska <biuro@biuromax.example>",
        subject="Zamówienie ABC-100, 15 szt.",
        body=(
            "Dzień dobry,\n\n"
            "chcielibyśmy zamówić 15 szt. ABC-100 z dostawą do końca miesiąca. "
            "Proszę o ofertę z cenami i warunkami płatności.\n\n"
            "Z poważaniem,\n"
            "Katarzyna Zielińska\n"
            "Biuro Max"
        ),
    ),
)


class FakeMailbox:
    """In-memory mailbox (no network); `messages` are oldest first."""

    name = "fake"

    def __init__(self, messages: Sequence[bytes] = DEMO_MESSAGES) -> None:
        self._messages = tuple(messages)

    def latest(self, limit: int) -> list[bytes]:
        if limit <= 0:
            return []
        return list(reversed(self._messages[-limit:]))


class UnconfiguredMailbox:
    """Stands in for `imap` without credentials; every call fails clearly."""

    name = "imap"

    def latest(self, limit: int) -> list[bytes]:
        raise MailboxNotConfigured("Mailbox not configured")


def get_mailbox(settings: Annotated[Settings, Depends(get_settings)]) -> Mailbox:
    """Mailbox selected by settings; also a FastAPI dependency overridable in tests."""
    if settings.mailbox_provider == "fake":
        return FakeMailbox()
    if (
        settings.imap_host is None
        or settings.imap_username is None
        or settings.imap_password is None
    ):
        return UnconfiguredMailbox()
    # Imported here: the IMAP client imports the errors defined above.
    from app.mailbox.imap import ImapMailbox

    return ImapMailbox(
        host=settings.imap_host,
        port=settings.imap_port,
        ssl=settings.imap_ssl,
        username=settings.imap_username,
        password=settings.imap_password.get_secret_value(),
        folder=settings.imap_folder,
        timeout_seconds=settings.imap_timeout_seconds,
    )
