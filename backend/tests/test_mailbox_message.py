import hashlib
from datetime import UTC, datetime, timedelta, timezone
from email.message import EmailMessage

import pytest

from app.mailbox import message
from app.mailbox.message import MailCandidate, Skipped, to_candidate

FETCHED_AT = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
SIGNATURE = "Pozdrawiam,\nMarek Nowak\nDział zakupów, ACME Sp. z o.o."


def _message(
    *,
    subject: str | None = "Zapytanie ofertowe",
    sender: str | None = "Marek Nowak <zakupy@acme.example>",
    message_id: str | None = "<abc-123@acme.example>",
    date: str | None = "Fri, 13 Nov 2026 09:30:00 +0100",
) -> EmailMessage:
    msg = EmailMessage()
    if sender is not None:
        msg["From"] = sender
    msg["To"] = "sprzedaz@firma.example"
    if subject is not None:
        msg["Subject"] = subject
    if message_id is not None:
        msg["Message-ID"] = message_id
    if date is not None:
        msg["Date"] = date
    return msg


def _plain(body: str, **headers: str | None) -> bytes:
    msg = _message(**headers)
    msg.set_content(body)
    return msg.as_bytes()


def _candidate(raw: bytes) -> MailCandidate:
    result = to_candidate(raw, fetched_at=FETCHED_AT)
    assert isinstance(result, MailCandidate)
    return result


def test_polish_plain_text_keeps_signature() -> None:
    body = (
        f"Dzień dobry,\n\nprosimy o ofertę na 80 szt. ABC-100 z dostawą do piątku.\n\n{SIGNATURE}"
    )

    candidate = _candidate(_plain(body))

    assert candidate == MailCandidate(
        external_id=hashlib.sha256(
            b"<abc-123@acme.example>\nzakupy@acme.example\nZapytanie ofertowe"
        ).hexdigest(),
        sender_name="Marek Nowak",
        sender_email="zakupy@acme.example",
        subject="Zapytanie ofertowe",
        body=body,
        received_at=datetime(2026, 11, 13, 9, 30, tzinfo=timezone(timedelta(hours=1))),
    )
    assert candidate.body.splitlines()[-1] == "Dział zakupów, ACME Sp. z o.o."


def test_multipart_alternative_prefers_plain() -> None:
    msg = _message()
    msg.set_content("Tekst zwykły.\n\nPozdrawiam,\nACME")
    msg.add_alternative("<p>Tekst <b>HTML</b>.</p>", subtype="html")

    assert _candidate(msg.as_bytes()).body == "Tekst zwykły.\n\nPozdrawiam,\nACME"


def test_html_only_becomes_text() -> None:
    msg = _message()
    msg.set_content(
        "<html><head><style>p { color: red; }</style><script>alert(1)</script></head>"
        "<body><div>Dzień dobry,</div>\n<p>prosimy o ofertę\n   na 20 szt.&nbsp;ABC-200.</p>"
        "<ul><li>dostawa do piątku</li><li>płatność 14 dni</li></ul>"
        "<p>Pozdrawiam,<br>Katarzyna Zielińska<br/>Biuro Max</p></body></html>",
        subtype="html",
    )

    body = _candidate(msg.as_bytes()).body

    assert "color" not in body
    assert "alert" not in body
    assert "<" not in body
    # Source line breaks and indentation (and &nbsp;) are one space.
    assert "prosimy o ofertę na 20 szt. ABC-200." in body
    assert "dostawa do piątku\n" in body
    assert body.endswith("Pozdrawiam,\nKatarzyna Zielińska\nBiuro Max")


def test_rfc2047_subject_and_name_are_decoded() -> None:
    raw = (
        b"From: =?utf-8?b?S2F0YXJ6eW5hIFppZWxpxYRza2E=?= <biuro@biuromax.example>\r\n"
        b"Subject: =?utf-8?q?Zam=C3=B3wienie_ABC-200=2C?= =?utf-8?q?_20_szt.?=\r\n"
        b"Message-ID: <x@biuromax.example>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Tre\xc5\x9b\xc4\x87.\r\n"
    )

    candidate = _candidate(raw)

    assert candidate.sender_name == "Katarzyna Zielińska"
    assert candidate.subject == "Zamówienie ABC-200, 20 szt."
    assert candidate.body == "Treść."


def test_reply_quote_and_quoted_lines_are_cut() -> None:
    body = (
        "Dzień dobry,\n\n"
        "> wcześniejsza wiadomość\n"
        "potwierdzamy 80 szt. ABC-100.\n\n\n\n\n"
        f"{SIGNATURE}\n\n"
        "W dniu 12.11.2026 o 10:00, Anna Kowalska <sprzedaz@firma.example> napisał:\n"
        "> Czy potwierdzają Państwo ilość?\n"
        "> Pozdrawiam, Anna\n"
    )

    candidate = _candidate(_plain(body))

    assert candidate.body == (f"Dzień dobry,\n\npotwierdzamy 80 szt. ABC-100.\n\n\n{SIGNATURE}")


def test_original_message_separator_is_cut() -> None:
    body = "Proszę o ofertę.\n\nACME\n\n-----Original Message-----\nFrom: someone\n"

    assert _candidate(_plain(body)).body == "Proszę o ofertę.\n\nACME"


def test_reused_message_id_from_another_sender_or_subject_is_not_a_duplicate() -> None:
    first = _candidate(_plain("Pierwsze zapytanie."))
    same_again = _candidate(_plain("Pierwsze zapytanie."))
    other_sender = _candidate(_plain("Inne.", sender="Jan <biuro@biuromax.example>"))
    other_subject = _candidate(_plain("Inne.", subject="Kolejne zapytanie"))

    assert same_again.external_id == first.external_id
    assert len({first.external_id, other_sender.external_id, other_subject.external_id}) == 3


def test_without_message_id_hashes_raw_bytes() -> None:
    raw = _plain("Treść.", message_id=None)

    assert _candidate(raw).external_id == hashlib.sha256(raw).hexdigest()


def test_without_sender_is_skipped() -> None:
    assert to_candidate(_plain("Treść.", sender=None), fetched_at=FETCHED_AT) == Skipped(
        "no_sender"
    )


def test_sender_without_at_is_skipped() -> None:
    raw = _plain("Treść.", sender="Marek Nowak <zakupy>")

    assert to_candidate(raw, fetched_at=FETCHED_AT) == Skipped("no_sender")


def test_sender_without_name_uses_address() -> None:
    assert _candidate(_plain("Treść.", sender="zakupy@acme.example")).sender_name == (
        "zakupy@acme.example"
    )


def test_date_without_zone_is_utc() -> None:
    raw = _plain("Treść.", date="Fri, 13 Nov 2026 09:30:00 -0000")

    assert _candidate(raw).received_at == datetime(2026, 11, 13, 9, 30, tzinfo=UTC)


def test_missing_or_invalid_date_is_fetch_time() -> None:
    assert _candidate(_plain("Treść.", date=None)).received_at == FETCHED_AT
    assert _candidate(_plain("Treść.", date="not a date")).received_at == FETCHED_AT
    # Year out of range: `parsedate_to_datetime` raises OverflowError, not ValueError.
    overflow = _plain("Treść.", date=None).replace(
        b"\nMessage-ID:", b"\nDate: Fri, 13 Nov 99999999999 09:30:00 +0000\nMessage-ID:"
    )
    assert b"99999999999" in overflow
    assert _candidate(overflow).received_at == FETCHED_AT


def test_date_in_the_future_is_fetch_time() -> None:
    raw = _plain("Treść.", date="Sat, 13 Nov 2027 09:30:00 +0000")

    assert _candidate(raw).received_at == FETCHED_AT


def test_eval_prefixed_subject_gets_mail_prefix() -> None:
    assert _candidate(_plain("Treść.", subject="[eval] x")).subject == "[mail] [eval] x"


def test_empty_subject_and_whitespace() -> None:
    assert _candidate(_plain("Treść.", subject=None)).subject == "(no subject)"
    assert _candidate(_plain("Treść.", subject="  a \t  b  ")).subject == "a b"


def test_long_subject_is_truncated_to_300() -> None:
    subject = _candidate(_plain("Treść.", subject="x" * 400)).subject

    assert len(subject) == 300
    assert subject == "x" * 299 + "…"


def test_long_body_is_limited() -> None:
    assert len(_candidate(_plain("y" * 25_000)).body) == 20_000


def test_huge_html_body_is_cut_before_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    parsed_lengths: list[int] = []
    html_to_text = message._html_to_text

    def recording(html: str) -> str:
        parsed_lengths.append(len(html))
        return html_to_text(html)

    monkeypatch.setattr(message, "_html_to_text", recording)
    msg = _message()
    msg.set_content("<p>" + "z" * (message.RAW_BODY_LIMIT * 3) + "</p>", subtype="html")

    body = _candidate(msg.as_bytes()).body

    assert parsed_lengths == [message.RAW_BODY_LIMIT]
    assert len(body) == message.BODY_LIMIT


def test_without_text_part_body_is_empty() -> None:
    msg = _message()
    msg.set_content(b"\x00\x01", maintype="application", subtype="octet-stream")

    assert _candidate(msg.as_bytes()).body == ""


def test_unreadable_message_is_skipped() -> None:
    raw = (
        b"From: zakupy@acme.example\r\n"
        b"Content-Type: text/plain; charset=no-such-charset\r\n"
        b"\r\n"
        b"Tresc.\r\n"
    )

    assert to_candidate(raw, fetched_at=FETCHED_AT) == Skipped("unreadable")
