"""Users, sessions and inquiries, with demo accounts and sample inquiries.

Revision ID: 0003_users_inquiries
Revises: 0002_step_tracing
Create Date: 2026-11-09

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0003_users_inquiries"
down_revision: str | Sequence[str] | None = "0002_step_tracing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_CREATED_AT = datetime(2026, 11, 9, tzinfo=UTC)

# Demo accounts start without a password; `python -m app.auth.demo_accounts` sets the
# hash from DEMO_PASSWORD on every start.
DEMO_USERS = [
    {
        "username": "sales",
        "display_name": "Anna Kowalska",
        "role": "salesperson",
        "password_hash": None,
        "created_at": SEED_CREATED_AT,
    },
    {
        "username": "supervisor",
        "display_name": "Piotr Wiśniewski",
        "role": "supervisor",
        "password_hash": None,
        "created_at": SEED_CREATED_AT,
    },
]

# Fictional companies; addresses use the reserved .example domain (RFC 2606).
SAMPLE_INQUIRIES = [
    {
        "sender_name": "Marek Nowak (ACME Sp. z o.o.)",
        "sender_email": "zakupy@acme.example",
        "subject": "Zapytanie ofertowe: 80 szt. ABC-100",
        "body": (
            "Dzień dobry,\n\n"
            "prosimy o ofertę na 80 szt. ABC-100 z dostawą do piątku. "
            "Jeśli nie mają Państwo pełnej ilości, możemy przyjąć podobny model "
            "o zbliżonych parametrach.\n\n"
            "Prosimy o najlepszą cenę i informację o terminie dostawy.\n\n"
            "Pozdrawiam,\n"
            "Marek Nowak\n"
            "Dział zakupów, ACME Sp. z o.o."
        ),
        "received_at": datetime(2026, 11, 2, 8, 15, tzinfo=UTC),
    },
    {
        "sender_name": "Katarzyna Zielińska (Biuro Max)",
        "sender_email": "biuro@biuromax.example",
        "subject": "Zamówienie ABC-200, 20 szt.",
        "body": (
            "Dzień dobry,\n\n"
            "chcielibyśmy zamówić 20 szt. ABC-200 z dostawą do końca miesiąca. "
            "Proszę o przesłanie oferty z cenami i warunkami płatności.\n\n"
            "Z poważaniem,\n"
            "Katarzyna Zielińska\n"
            "Biuro Max"
        ),
        "received_at": datetime(2026, 11, 3, 10, 40, tzinfo=UTC),
    },
    {
        "sender_name": "Tomasz Lewandowski (Hurtownia Delta)",
        "sender_email": "handel@hurtowniadelta.example",
        "subject": "500 szt. ABC-100 — prośba o rabat",
        "body": (
            "Dzień dobry,\n\n"
            "jesteśmy zainteresowani zakupem 500 szt. ABC-100. "
            "Przy takiej ilości prosimy o rabat 25% od ceny katalogowej.\n\n"
            "Czekamy na ofertę z terminem realizacji.\n\n"
            "Pozdrawiam,\n"
            "Tomasz Lewandowski\n"
            "Hurtownia Delta"
        ),
        "received_at": datetime(2026, 11, 4, 13, 5, tzinfo=UTC),
    },
    {
        "sender_name": "Ewa Kamińska (Technika Omega)",
        "sender_email": "zaopatrzenie@technikaomega.example",
        "subject": "Pilne: 120 szt. XYZ-300",
        "body": (
            "Dzień dobry,\n\n"
            "potrzebujemy 120 szt. XYZ-300 w ciągu tygodnia. "
            "Interesuje nas wyłącznie oryginalny produkt — nie akceptujemy zamienników.\n\n"
            "Proszę o potwierdzenie dostępności i cenę.\n\n"
            "Z poważaniem,\n"
            "Ewa Kamińska\n"
            "Zaopatrzenie, Technika Omega"
        ),
        "received_at": datetime(2026, 11, 5, 9, 30, tzinfo=UTC),
    },
]


def upgrade() -> None:
    users = op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.CheckConstraint("role IN ('salesperson', 'supervisor')", name="ck_users_role"),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    inquiries = op.create_table(
        "inquiries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_name", sa.String(length=200), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inquiries_received_at", "inquiries", ["received_at"])

    op.bulk_insert(users, DEMO_USERS)
    op.bulk_insert(inquiries, SAMPLE_INQUIRIES)


def downgrade() -> None:
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_inquiries_received_at", table_name="inquiries")
    op.drop_table("inquiries")
    op.drop_table("users")
