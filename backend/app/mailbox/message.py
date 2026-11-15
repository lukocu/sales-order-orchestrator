"""Turn a raw RFC 5322 message into the data of an inquiry, or a reason to skip it.

The result fits the `inquiries` column limits and keeps the body parser-friendly: the quoted
reply is cut off, so the signature stays the last non-empty line. Nothing here logs or raises
with message content; an unparsable message is simply skipped as `unreadable`.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Literal

from app.eval.runner import SUBJECT_PREFIX

SENDER_NAME_LIMIT = 200
SENDER_EMAIL_LIMIT = 320
SUBJECT_LIMIT = 300
BODY_LIMIT = 20_000

NO_SUBJECT = "(no subject)"
# Keeps a mail subject from looking like an eval inquiry, which the eval cleanup deletes.
MAIL_SUBJECT_PREFIX = "[mail] "

SkipReason = Literal["no_sender", "unreadable"]

# First line of a quoted reply; everything from it on is cut off.
_QUOTE_HEADER = re.compile(
    r"^\s*(?:"
    r"On\s.*\bwrote:"
    r"|W dniu\s.*\bnapisał(?:a|\(a\))?:"
    r"|-{2,}\s*Original Message\s*-{2,}"
    r"|-{2,}\s*Oryginalna wiadomość\s*-{2,}"
    r")\s*$",
    re.IGNORECASE,
)
# Three or more empty (or blank) lines in a row.
_EXTRA_BLANK_LINES = re.compile(r"\n(?:[ \t]*\n){3,}")


@dataclass(frozen=True)
class MailCandidate:
    """Data of a new `mailbox` inquiry; `external_id` is the hex SHA-256 of the message id."""

    external_id: str
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime


@dataclass(frozen=True)
class Skipped:
    reason: SkipReason


def to_candidate(raw: bytes, *, fetched_at: datetime) -> MailCandidate | Skipped:
    """The inquiry data of the message, or why it is skipped. Never raises."""
    try:
        return _convert(raw, fetched_at)
    except Exception:
        return Skipped("unreadable")


def _convert(raw: bytes, fetched_at: datetime) -> MailCandidate | Skipped:
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    assert isinstance(msg, EmailMessage)  # guaranteed by policy.default

    name, address = parseaddr(str(msg.get("From", "")))
    address = address.strip()
    if not address or "@" not in address or len(address) > SENDER_EMAIL_LIMIT:
        return Skipped("no_sender")

    return MailCandidate(
        external_id=_external_id(msg, raw),
        sender_name=(" ".join(name.split()) or address)[:SENDER_NAME_LIMIT],
        sender_email=address,
        subject=_subject(msg),
        body=_body(msg),
        received_at=_received_at(msg, fetched_at),
    )


def _external_id(msg: EmailMessage, raw: bytes) -> str:
    message_id = str(msg.get("Message-ID", "")).strip()
    source = message_id.encode() if message_id else raw
    return hashlib.sha256(source).hexdigest()


def _subject(msg: EmailMessage) -> str:
    subject = " ".join(str(msg.get("Subject", "")).split()) or NO_SUBJECT
    if subject.startswith(SUBJECT_PREFIX):
        subject = MAIL_SUBJECT_PREFIX + subject
    if len(subject) > SUBJECT_LIMIT:
        subject = subject[: SUBJECT_LIMIT - 1] + "…"
    return subject


def _received_at(msg: EmailMessage, fetched_at: datetime) -> datetime:
    value = str(msg.get("Date", "")).strip()
    if not value:
        return fetched_at
    try:
        received_at = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return fetched_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    return received_at


def _body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    assert isinstance(part, EmailMessage)
    content = part.get_content()
    if not isinstance(content, str):
        return ""
    if part.get_content_type() == "text/html":
        content = _html_to_text(content)
    return _clean(content)


def _clean(text: str) -> str:
    """Cut the quoted reply, drop `>` lines, normalise line breaks, limit the length."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if _QUOTE_HEADER.match(line):
            lines = lines[:index]
            break
    text = "\n".join(line for line in lines if not line.startswith(">"))
    text = _EXTRA_BLANK_LINES.sub("\n\n\n", text).strip()
    return text[:BODY_LIMIT]


class _HtmlText(HTMLParser):
    """Text of an HTML body: no `script`/`style`, line breaks at `br`, `p`, `div` and `li`."""

    _SKIPPED = frozenset({"script", "style"})
    _BREAKS = frozenset({"br", "p", "div", "li"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIPPED:
            self._skip_depth += 1
        elif tag in self._BREAKS:
            self._parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BREAKS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIPPED:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._BREAKS and tag != "br":
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            # Source formatting is not layout: whitespace runs are one space.
            self._parts.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        return "\n".join(line.strip() for line in "".join(self._parts).split("\n"))


def _html_to_text(html: str) -> str:
    parser = _HtmlText()
    parser.feed(html)
    parser.close()
    return parser.text()
