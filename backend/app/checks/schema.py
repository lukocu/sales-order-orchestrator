"""Shape of a check result, stored as JSONB in `inquiry_checks.results`.

Written with `CheckResults.model_dump(mode="json")` and read with `model_validate`. Any later
change to these models needs a data migration of the stored rows, or a new optional field
with a default (context/foundation/lessons.md).
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.parsing.schema import PriceKind

Outcome = Literal["standard", "exception", "needs_input"]
ExceptionType = Literal["insufficient_stock"]
NeedsInputReason = Literal[
    "customer_missing",
    "customer_not_found",
    "customer_ambiguous",
    "product_missing",
    "product_not_found",
    "quantity_missing",
]

CustomerStatus = Literal["matched", "missing", "not_found", "ambiguous"]
MatchedBy = Literal["name", "email"]
StockStatus = Literal["ok", "insufficient", "skipped"]
PriceStatus = Literal["ok", "skipped"]
DiscountStatus = Literal["ok", "above_standard", "skipped"]
CreditStatus = Literal["ok", "over_limit", "blocked", "skipped"]


class CustomerCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CustomerStatus
    matched_by: MatchedBy | None = None
    customer_id: int | None = None
    name: str | None = None
    candidates: list[str] = Field(default_factory=list)  # names when ambiguous


class StockCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StockStatus
    product_code: str | None = None  # catalogue code when found, else as requested
    product_name: str | None = None
    requested: int | None = None
    available: int | None = None
    shortage: int | None = None


class PriceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PriceStatus
    list_price: Decimal | None = None
    discount_percent: Decimal | None = None  # the customer's standard discount
    unit_price: Decimal | None = None
    total: Decimal | None = None  # None without a quantity
    currency: Literal["PLN"] = "PLN"


class DiscountCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DiscountStatus
    standard_percent: Decimal | None = None
    requested_kind: PriceKind = "none"
    requested_value: Decimal | None = None


class CreditCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CreditStatus
    limit: Decimal | None = None
    balance: Decimal | None = None
    order_value: Decimal | None = None


class CheckResults(BaseModel):
    """Every single check of one run. The outcome is stored in `inquiry_checks` columns."""

    model_config = ConfigDict(extra="forbid")

    customer: CustomerCheck
    stock: StockCheck
    price: PriceCheck
    discount: DiscountCheck
    credit: CreditCheck
    reasons: list[NeedsInputReason] = Field(default_factory=list)
