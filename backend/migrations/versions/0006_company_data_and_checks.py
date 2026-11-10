"""Company data (customers, products with stock) and the check result of an inquiry.

Revision ID: 0006_company_data_and_checks
Revises: 0005_inquiry_analyses_run_index
Create Date: 2026-11-10

"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_company_data_and_checks"
down_revision: str | Sequence[str] | None = "0005_inquiry_analyses_run_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Simulated records matching the seed inquiries of 0003_users_inquiries. Names carry no
# legal form, so they match the signature variants ("ACME Sp. z o.o." contains "ACME").
SEED_CUSTOMERS = [
    {
        "name": "ACME",
        "email_domain": "acme.example",
        "standard_discount_percent": Decimal("5.00"),
        "credit_limit": Decimal("30000.00"),
        "credit_balance": Decimal("2000.00"),
        "credit_blocked": False,
    },
    {
        "name": "Biuro Max",
        "email_domain": "biuromax.example",
        "standard_discount_percent": Decimal("0.00"),
        "credit_limit": Decimal("10000.00"),
        "credit_balance": Decimal("0.00"),
        "credit_blocked": False,
    },
    {
        # 500 x 108.00 = 54 000.00 is over the limit: the seed shows `over_limit`.
        "name": "Hurtownia Delta",
        "email_domain": "hurtowniadelta.example",
        "standard_discount_percent": Decimal("10.00"),
        "credit_limit": Decimal("50000.00"),
        "credit_balance": Decimal("0.00"),
        "credit_blocked": False,
    },
    {
        "name": "Technika Omega",
        "email_domain": "technikaomega.example",
        "standard_discount_percent": Decimal("3.00"),
        "credit_limit": Decimal("40000.00"),
        "credit_balance": Decimal("5000.00"),
        "credit_blocked": False,
    },
]

SEED_PRODUCTS = [
    {
        "code": "ABC-100",
        "name": "Czujnik ciśnienia ABC-100",
        "list_price": Decimal("120.00"),
        "stock_quantity": 50,
    },
    {
        "code": "ABC-200",
        "name": "Moduł sterujący ABC-200",
        "list_price": Decimal("85.00"),
        "stock_quantity": 150,
    },
    {
        "code": "XYZ-300",
        "name": "Zawór proporcjonalny XYZ-300",
        "list_price": Decimal("240.00"),
        "stock_quantity": 60,
    },
]


def upgrade() -> None:
    customers = op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email_domain", sa.String(length=255), nullable=False),
        sa.Column("standard_discount_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("credit_limit", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("credit_balance", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("credit_blocked", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_customers_name"),
        sa.UniqueConstraint("email_domain", name="uq_customers_email_domain"),
        sa.CheckConstraint(
            "standard_discount_percent >= 0 AND standard_discount_percent <= 100",
            name="ck_customers_standard_discount_percent",
        ),
        sa.CheckConstraint("credit_limit >= 0", name="ck_customers_credit_limit"),
        sa.CheckConstraint("credit_balance >= 0", name="ck_customers_credit_balance"),
    )

    products = op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("list_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_products_code"),
        sa.CheckConstraint("list_price > 0", name="ck_products_list_price"),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_products_stock_quantity"),
    )

    op.create_table(
        "inquiry_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("analysis_version", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("exception_type", sa.String(length=30), nullable=True),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["trace_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("inquiry_id", name="uq_inquiry_checks_inquiry_id"),
        sa.CheckConstraint(
            "outcome IN ('standard', 'exception', 'needs_input')",
            name="ck_inquiry_checks_outcome",
        ),
        sa.CheckConstraint(
            "exception_type IN ('insufficient_stock')", name="ck_inquiry_checks_exception_type"
        ),
        sa.CheckConstraint(
            "(outcome = 'exception') = (exception_type IS NOT NULL)",
            name="ck_inquiry_checks_exception_type_with_outcome",
        ),
    )
    op.create_index("ix_inquiry_checks_run_id", "inquiry_checks", ["run_id"])

    op.bulk_insert(customers, SEED_CUSTOMERS)
    op.bulk_insert(products, SEED_PRODUCTS)


def downgrade() -> None:
    op.drop_index("ix_inquiry_checks_run_id", table_name="inquiry_checks")
    op.drop_table("inquiry_checks")
    op.drop_table("products")
    op.drop_table("customers")
