from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.checks.schema import ExceptionType, Outcome

# Enum-like columns are VARCHAR with a CHECK constraint; Outcome and ExceptionType mirror them.
ENUM_LENGTH = 30


class Customer(SQLModel, table=True):
    """Customer record (simulated company data, seeded by a migration)."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("name", name="uq_customers_name"),
        UniqueConstraint("email_domain", name="uq_customers_email_domain"),
        CheckConstraint(
            "standard_discount_percent >= 0 AND standard_discount_percent <= 100",
            name="ck_customers_standard_discount_percent",
        ),
        CheckConstraint("credit_limit >= 0", name="ck_customers_credit_limit"),
        CheckConstraint("credit_balance >= 0", name="ck_customers_credit_balance"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)  # without the legal form, e.g. "ACME"
    email_domain: str = Field(max_length=255)  # lower case, e.g. "acme.example"
    standard_discount_percent: Decimal = Field(sa_type=Numeric(5, 2))
    credit_limit: Decimal = Field(sa_type=Numeric(12, 2))  # PLN
    credit_balance: Decimal = Field(sa_type=Numeric(12, 2))  # PLN, amount already owed
    credit_blocked: bool


class Product(SQLModel, table=True):
    """Catalogue product with its current stock (simulated company data)."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("code", name="uq_products_code"),
        CheckConstraint("list_price > 0", name="ck_products_list_price"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_quantity"),
        CheckConstraint("unit_cost > 0", name="ck_products_unit_cost"),
    )

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=50)
    name: str = Field(max_length=200)
    list_price: Decimal = Field(sa_type=Numeric(12, 2))  # PLN net
    stock_quantity: int
    unit_cost: Decimal = Field(sa_type=Numeric(12, 2))  # PLN net, cost of own stock


class InquiryChecks(SQLModel, table=True):
    """The current check result of an inquiry; a new check run replaces it.

    `results` holds `CheckResults.model_dump(mode="json")` (Decimal as strings) and is read
    back with `CheckResults.model_validate`. The outcome lives only in the columns.
    """

    __tablename__ = "inquiry_checks"
    __table_args__ = (
        UniqueConstraint("inquiry_id", name="uq_inquiry_checks_inquiry_id"),
        CheckConstraint(
            "outcome IN ('standard', 'exception', 'needs_input')",
            name="ck_inquiry_checks_outcome",
        ),
        CheckConstraint(
            "exception_type IN ('insufficient_stock')", name="ck_inquiry_checks_exception_type"
        ),
        CheckConstraint(
            "(outcome = 'exception') = (exception_type IS NOT NULL)",
            name="ck_inquiry_checks_exception_type_with_outcome",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiries.id", ondelete="CASCADE")
    run_id: int | None = Field(
        default=None, foreign_key="trace_runs.id", ondelete="SET NULL", index=True
    )
    # corrected_at of the analysis the checks used, or analyzed_at when it has no corrections.
    analysis_version: datetime = Field(sa_type=DateTime(timezone=True))
    outcome: Outcome = Field(sa_type=String(ENUM_LENGTH))
    exception_type: ExceptionType | None = Field(default=None, sa_type=String(ENUM_LENGTH))
    results: dict[str, Any] = Field(sa_type=JSONB)
    checked_at: datetime = Field(sa_type=DateTime(timezone=True))
