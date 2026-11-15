"""Put three sample inquiries into the local GreenMail mailbox (IMAP APPEND).

    docker compose --profile mail up -d mail
    docker compose run --rm backend uv run python -m app.mailbox.demo

Only for the local development mailbox: it refuses (exit code 2) unless MAILBOX_PROVIDER is
`imap`, IMAP_SSL is off, IMAP_HOST is `mail`, `localhost` or `127.0.0.1` and the username and
password are set. Every run appends new copies; the messages have fixed Message-IDs, so
"Fetch mail" stores each of them once. Output carries counts only, never message content,
credentials or server responses.
"""

import contextlib
import imaplib
import sys
from email.message import EmailMessage

from app.settings import Settings, get_settings

LOCAL_HOSTS = frozenset({"mail", "localhost", "127.0.0.1"})

# Bound at import: tests replace `imaplib.IMAP4` / `IMAP4_SSL` with stand-ins.
_IMAP_ERROR = imaplib.IMAP4.error


def _plain_with_signature() -> bytes:
    msg = EmailMessage()
    msg["From"] = "Tomasz Lewandowski <handel@hurtowniadelta.example>"
    msg["To"] = "sprzedaz@firma.example"
    msg["Subject"] = "Zapytanie: 200 szt. ABC-200"
    msg["Date"] = "Fri, 13 Nov 2026 08:30:00 +0100"
    msg["Message-ID"] = "<greenmail-demo-1@hurtowniadelta.example>"
    msg.set_content(
        "Dzień dobry,\n\n"
        "prosimy o ofertę na 200 szt. ABC-200 z dostawą do końca miesiąca. "
        "Przy takiej ilości prosimy o rabat 12% od ceny katalogowej.\n\n"
        "Czekamy na ofertę z terminem realizacji.\n\n"
        "Pozdrawiam,\n"
        "Tomasz Lewandowski\n"
        "Hurtownia Delta"
    )
    return msg.as_bytes()


def _html_only() -> bytes:
    msg = EmailMessage()
    msg["From"] = "Ewa Kamińska <zaopatrzenie@technikaomega.example>"
    msg["To"] = "sprzedaz@firma.example"
    msg["Subject"] = "Pilne: 30 szt. XYZ-300"
    msg["Date"] = "Fri, 13 Nov 2026 12:10:00 +0100"
    msg["Message-ID"] = "<greenmail-demo-2@technikaomega.example>"
    msg.set_content(
        "<html><head><style>p { margin: 0 0 1em; }</style></head><body>"
        "<p>Dzień dobry,</p>"
        "<p>potrzebujemy <b>30 szt. XYZ-300</b> do piątku. "
        "Interesuje nas wyłącznie oryginalny produkt — nie akceptujemy zamienników.</p>"
        "<p>Proszę o potwierdzenie dostępności i cenę.</p>"
        "<p>Z poważaniem,<br>Ewa Kamińska<br>Zaopatrzenie, Technika Omega</p>"
        "</body></html>",
        subtype="html",
    )
    return msg.as_bytes()


def _reply_with_quote() -> bytes:
    msg = EmailMessage()
    msg["From"] = "Marek Nowak <zakupy@acme.example>"
    msg["To"] = "sprzedaz@firma.example"
    msg["Subject"] = "Re: Zapytanie ofertowe: 60 szt. ABC-100"
    msg["Date"] = "Sat, 14 Nov 2026 09:05:00 +0100"
    msg["Message-ID"] = "<greenmail-demo-3@acme.example>"
    msg["In-Reply-To"] = "<oferta-60@firma.example>"
    msg.set_content(
        "Dzień dobry,\n\n"
        "potwierdzamy zapotrzebowanie na 60 szt. ABC-100 z dostawą do piątku. "
        "Jeśli nie mają Państwo pełnej ilości, możemy przyjąć podobny model.\n\n"
        "Prosimy o najlepszą cenę.\n\n"
        "Pozdrawiam,\n"
        "Marek Nowak\n"
        "Dział zakupów, ACME Sp. z o.o.\n\n"
        "W dniu 13.11.2026 o 16:20, Dział sprzedaży <sprzedaz@firma.example> napisał:\n"
        "> Dzień dobry,\n"
        ">\n"
        "> czy mogą Państwo potwierdzić ilość i termin dostawy?\n"
        ">\n"
        "> Pozdrawiamy,\n"
        "> Dział sprzedaży\n"
    )
    return msg.as_bytes()


# Fictional companies and the reserved .example domain (RFC 2606), oldest first.
DEMO_MAILS: tuple[bytes, ...] = (_plain_with_signature(), _html_only(), _reply_with_quote())


def refusal_reason(settings: Settings) -> str | None:
    """Why the settings do not point at the local development mailbox, or None."""
    if settings.mailbox_provider != "imap":
        return "MAILBOX_PROVIDER is not imap."
    if settings.imap_ssl:
        return "IMAP_SSL is on; the local GreenMail mailbox is plain IMAP (IMAP_SSL=false)."
    if settings.imap_host not in LOCAL_HOSTS:
        return "IMAP_HOST is not a local development host (mail, localhost, 127.0.0.1)."
    if settings.imap_username is None or settings.imap_password is None:
        return "IMAP_USERNAME and IMAP_PASSWORD must be set."
    return None


def append_demo_mails(settings: Settings) -> int:
    """Append `DEMO_MAILS` to IMAP_FOLDER; returns how many the server accepted.

    Call only after `refusal_reason` returned None. Raises `imaplib.IMAP4.error` or
    `OSError` when the server cannot be reached or rejects the login.
    """
    assert settings.imap_host is not None
    assert settings.imap_username is not None
    assert settings.imap_password is not None
    connection = imaplib.IMAP4(
        settings.imap_host, settings.imap_port, timeout=settings.imap_timeout_seconds
    )
    try:
        connection.login(settings.imap_username, settings.imap_password.get_secret_value())
        appended = 0
        for raw in DEMO_MAILS:
            status, _ = connection.append(settings.imap_folder, None, None, raw)
            if status == "OK":
                appended += 1
        return appended
    finally:
        with contextlib.suppress(_IMAP_ERROR, OSError):
            connection.logout()


def main() -> int:
    settings = get_settings()
    reason = refusal_reason(settings)
    if reason is not None:
        print(f"Refusing to write sample mail: {reason}", file=sys.stderr)
        print("This tool only fills the local GreenMail mailbox (see README).", file=sys.stderr)
        return 2
    try:
        appended = append_demo_mails(settings)
    # Class names only: imaplib errors can quote the server's answer.
    except _IMAP_ERROR:
        print("The IMAP server rejected the login or the command.", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Mailbox unavailable ({type(error).__name__}).", file=sys.stderr)
        return 1
    print(f"Appended {appended} of {len(DEMO_MAILS)} sample messages.")
    return 0 if appended == len(DEMO_MAILS) else 1


if __name__ == "__main__":
    sys.exit(main())
