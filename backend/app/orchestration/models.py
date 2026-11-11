from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.orchestration.schema import Compatibility, OrchestrationStatus

# Enum-like columns are VARCHAR with a CHECK constraint; Compatibility and OrchestrationStatus
# mirror them.
ENUM_LENGTH = 30


class ProductSubstitute(SQLModel, table=True):
    """A product that can replace another one (simulated company data, seeded by a migration)."""

    __tablename__ = "product_substitutes"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "substitute_product_id",
            name="uq_product_substitutes_product_id_substitute_product_id",
        ),
        CheckConstraint(
            "compatibility IN ('full', 'partial')", name="ck_product_substitutes_compatibility"
        ),
        CheckConstraint(
            "product_id <> substitute_product_id", name="ck_product_substitutes_not_self"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id")
    substitute_product_id: int = Field(foreign_key="products.id")
    compatibility: Compatibility = Field(sa_type=String(ENUM_LENGTH))
    note: str = Field(max_length=200)


class SupplierOffer(SQLModel, table=True):
    """Stock a supplier can deliver (simulated company data)."""

    __tablename__ = "supplier_offers"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_supplier_offers_quantity"),
        CheckConstraint("lead_time_days >= 0", name="ck_supplier_offers_lead_time_days"),
        CheckConstraint("unit_cost > 0", name="ck_supplier_offers_unit_cost"),
        # One offer per supplier and product: option ids and costs are keyed by the pair.
        UniqueConstraint(
            "product_id", "supplier_name", name="uq_supplier_offers_product_id_supplier_name"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id")
    supplier_name: str = Field(max_length=200)
    quantity: int
    # Counted from the inquiry's reference_date, so a result does not depend on the run day.
    lead_time_days: int
    unit_cost: Decimal = Field(sa_type=Numeric(12, 2))  # PLN net, purchase price per unit


class CustomerOrder(SQLModel, table=True):
    """A past order of a customer (simulated company data)."""

    __tablename__ = "customer_orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_customer_orders_quantity"),
        CheckConstraint(
            "(substitute_accepted IS NULL) = (NOT substitute_offered)",
            name="ck_customer_orders_substitute_accepted_with_offered",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    product_id: int = Field(foreign_key="products.id")
    quantity: int
    ordered_on: date
    substitute_offered: bool
    # None exactly when no substitute was offered.
    substitute_accepted: bool | None = None


class InquiryOrchestration(SQLModel, table=True):
    """The current orchestration result of an inquiry; a new run replaces it.

    `result` holds the orchestration result dumped with `model_dump(mode="json")` and is read
    back with `model_validate`. The status lives only in its column.
    """

    __tablename__ = "inquiry_orchestrations"
    __table_args__ = (
        UniqueConstraint("inquiry_id", name="uq_inquiry_orchestrations_inquiry_id"),
        CheckConstraint(
            "status IN ('completed', 'partial', 'failed')",
            name="ck_inquiry_orchestrations_status",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiries.id", ondelete="CASCADE")
    run_id: int | None = Field(
        default=None, foreign_key="trace_runs.id", ondelete="SET NULL", index=True
    )
    # The analysis version (corrected_at, else analyzed_at) the orchestration used.
    analysis_version: datetime = Field(sa_type=DateTime(timezone=True))
    # `checked_at` of the check result the orchestration used; a re-check replaces it.
    checks_checked_at: datetime = Field(sa_type=DateTime(timezone=True))
    status: OrchestrationStatus = Field(sa_type=String(ENUM_LENGTH))
    result: dict[str, Any] = Field(sa_type=JSONB)
    orchestrated_at: datetime = Field(sa_type=DateTime(timezone=True))
