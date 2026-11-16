"""Read-only IMAP client: the newest messages of one folder, without changing any flag.

The folder is opened with `EXAMINE` (`select(..., readonly=True)`) and messages are fetched
with `BODY.PEEK[]`, so `\\Seen` stays as it was. `imaplib` errors can quote the server's
answer, so they are mapped to the mailbox errors with constant messages and not chained.
"""

import contextlib
import imaplib
import re
import ssl
from typing import Any

from app.mailbox.client import (
    MailboxAuthFailed,
    MailboxError,
    MailboxProtocolError,
    MailboxUnavailable,
)

# Bound at import: tests replace `imaplib.IMAP4` / `IMAP4_SSL` with stand-ins.
_IMAP_ERROR = imaplib.IMAP4.error
_IMAP_ABORT = imaplib.IMAP4.abort

# Leading message sequence number of a FETCH response item (`b"12 (UID 40 BODY[] {…}"`).
_SEQUENCE_NUMBER = re.compile(rb"^\s*(\d+)\s")


class ImapMailbox:
    name = "imap"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        ssl: bool,
        username: str,
        password: str,
        folder: str,
        timeout_seconds: float,
    ) -> None:
        self._host = host
        self._port = port
        self._ssl = ssl
        self._username = username
        self._password = password
        self._folder = folder
        self._timeout_seconds = timeout_seconds

    def latest(self, limit: int) -> list[bytes]:
        if limit <= 0:
            return []
        try:
            return self._latest(limit)
        except MailboxError:
            raise
        # `abort` (a subclass of `error`) means the connection broke.
        except _IMAP_ABORT:
            raise MailboxUnavailable("Mailbox unavailable") from None
        except _IMAP_ERROR:
            raise MailboxProtocolError("Mailbox error") from None
        # Includes TimeoutError and ssl.SSLError.
        except OSError:
            raise MailboxUnavailable("Mailbox unavailable") from None

    def _connect(self) -> imaplib.IMAP4:
        if self._ssl:
            # imaplib's default context does not check the certificate or the host name.
            return imaplib.IMAP4_SSL(
                self._host,
                self._port,
                ssl_context=ssl.create_default_context(),
                timeout=self._timeout_seconds,
            )
        return imaplib.IMAP4(self._host, self._port, timeout=self._timeout_seconds)

    def _latest(self, limit: int) -> list[bytes]:
        connection = self._connect()
        try:
            try:
                connection.login(self._username, self._password)
            except _IMAP_ABORT:
                raise
            # UnicodeError: a non-ASCII password cannot be sent with LOGIN.
            except _IMAP_ERROR, UnicodeError:
                raise MailboxAuthFailed("Mailbox login failed") from None
            status, _ = connection.select(self._folder, readonly=True)
            _expect_ok(status)
            status, data = connection.uid("SEARCH", "ALL")
            _expect_ok(status)
            uids = _uids(data)[-limit:]
            if not uids:
                return []
            status, data = connection.uid("FETCH", b",".join(uids).decode(), "(BODY.PEEK[])")
            _expect_ok(status)
            return _newest_first(data)[:limit]
        finally:
            _logout(connection)


def _expect_ok(status: str) -> None:
    if status != "OK":
        raise MailboxProtocolError("Mailbox error")


def _uids(data: list[Any]) -> list[bytes]:
    """UIDs of a `UID SEARCH` answer, ascending as the server sends them."""
    first = data[0] if data else None
    if first is None:
        return []
    if not isinstance(first, bytes):
        raise MailboxProtocolError("Mailbox error")
    uids = first.split()
    if not all(uid.isdigit() for uid in uids):
        raise MailboxProtocolError("Mailbox error")
    return uids


def _newest_first(data: list[Any]) -> list[bytes]:
    """Message bytes of a `UID FETCH` answer, highest sequence number (= newest) first.

    Each message is a `(header, literal)` tuple; the closing `b")"` items are skipped.
    Sequence numbers grow with UIDs, and unlike the UID they always lead the item.
    """
    messages: list[tuple[int, bytes]] = []
    for item in data:
        if not isinstance(item, tuple):
            continue
        if len(item) != 2 or not isinstance(item[0], bytes) or not isinstance(item[1], bytes):
            raise MailboxProtocolError("Mailbox error")
        match = _SEQUENCE_NUMBER.match(item[0])
        if match is None:
            raise MailboxProtocolError("Mailbox error")
        messages.append((int(match.group(1)), item[1]))
    messages.sort(key=lambda message: message[0], reverse=True)
    return [raw for _, raw in messages]


def _logout(connection: imaplib.IMAP4) -> None:
    """Close the session; a failure here must not hide the result or quote the server."""
    with contextlib.suppress(_IMAP_ERROR, OSError):
        connection.logout()
