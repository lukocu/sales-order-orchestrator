"""Check rules as pure functions: no database, no model, no clock.

Inputs are the current `ParsedFields`, the sender's e-mail and immutable snapshots of the
company data. Each check is its own function, so the service can run each one as a separate
tracing step; `evaluate` runs them all in order.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.checks.schema import (
    CheckResults,
    CreditCheck,
    CreditStatus,
    CustomerCheck,
    DiscountCheck,
    ExceptionType,
    MatchedBy,
    NeedsInputReason,
    Outcome,
    PriceCheck,
    StockCheck,
)
from app.parsing.schema import ParsedFields

CENT = Decimal("0.01")
HUNDRED = Decimal(100)

# Legal forms removed before matching; spaces inside them are optional.
_LEGAL_FORMS = re.compile(
    r"(?<!\w)(?:sp\.\s*z\s*o\.\s*o\.|s\.\s*a\.|sp\.\s*j\.|sp\.\s*k\.)", re.IGNORECASE
)
_PUNCTUATION = re.compile(r"[^\w\s]")


@dataclass(frozen=True)
class CustomerRecord:
    id: int
    name: str
    email_domain: str
    standard_discount_percent: Decimal
    credit_limit: Decimal
    credit_balance: Decimal
    credit_blocked: bool


@dataclass(frozen=True)
class ProductRecord:
    id: int
    code: str
    name: str
    list_price: Decimal
    stock_quantity: int


@dataclass(frozen=True)
class Classification:
    outcome: Outcome
    exception_type: ExceptionType | None
    results: CheckResults


def normalize_name(text: str) -> list[str]:
    """Lower case, legal forms and punctuation removed, split into words."""
    without_forms = _LEGAL_FORMS.sub(" ", text.lower())
    return _PUNCTUATION.sub(" ", without_forms).split()


def _contains_words(haystack: list[str], needle: list[str]) -> bool:
    size = len(needle)
    if size == 0:
        return False
    return any(haystack[i : i + size] == needle for i in range(len(haystack) - size + 1))


def _email_domain(email: str) -> str | None:
    _, at, domain = email.strip().rpartition("@")
    domain = domain.strip().lower()
    return domain if at and domain else None


def _match_result(
    found: list[CustomerRecord], matched_by: MatchedBy, none_status: Literal["missing", "not_found"]
) -> tuple[CustomerCheck, CustomerRecord | None]:
    if len(found) == 1:
        (record,) = found
        check = CustomerCheck(
            status="matched", matched_by=matched_by, customer_id=record.id, name=record.name
        )
        return check, record
    if not found:
        return CustomerCheck(status=none_status), None
    candidates = sorted(record.name for record in found)
    return CustomerCheck(status="ambiguous", candidates=candidates), None


def match_customer(
    fields: ParsedFields, sender_email: str, customers: Sequence[CustomerRecord]
) -> tuple[CustomerCheck, CustomerRecord | None]:
    """Match by name when the field is filled, by the sender's domain only when it is empty.

    A filled field without a hit does not fall back to the e-mail: a salesperson's
    correction is the source of truth.
    """
    field_words = normalize_name(fields.customer or "")
    if field_words:
        by_name = [c for c in customers if _contains_words(field_words, normalize_name(c.name))]
        return _match_result(by_name, "name", "not_found")
    domain = _email_domain(sender_email)
    by_email = [c for c in customers if domain is not None and c.email_domain.lower() == domain]
    return _match_result(by_email, "email", "missing")


def find_product(fields: ParsedFields, products: Sequence[ProductRecord]) -> ProductRecord | None:
    code = (fields.product_code or "").strip().lower()
    if not code:
        return None
    return next((p for p in products if p.code.strip().lower() == code), None)


def check_stock(fields: ParsedFields, product: ProductRecord | None) -> StockCheck:
    """Needs only the product and the quantity, not the customer."""
    if product is None:
        requested_code = (fields.product_code or "").strip() or None
        return StockCheck(status="skipped", product_code=requested_code, requested=fields.quantity)
    if fields.quantity is None:
        return StockCheck(
            status="skipped",
            product_code=product.code,
            product_name=product.name,
            available=product.stock_quantity,
        )
    shortage = max(fields.quantity - product.stock_quantity, 0)
    return StockCheck(
        status="insufficient" if shortage > 0 else "ok",
        product_code=product.code,
        product_name=product.name,
        requested=fields.quantity,
        available=product.stock_quantity,
        shortage=shortage,
    )


def check_price(
    fields: ParsedFields, customer: CustomerRecord | None, product: ProductRecord | None
) -> PriceCheck:
    """List price less the customer's standard discount; total only with a quantity."""
    if customer is None or product is None:
        return PriceCheck(status="skipped")
    discount = customer.standard_discount_percent
    unit_price = (product.list_price * (HUNDRED - discount) / HUNDRED).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    total = None
    if fields.quantity is not None:
        total = (unit_price * fields.quantity).quantize(CENT, rounding=ROUND_HALF_UP)
    return PriceCheck(
        status="ok",
        list_price=product.list_price,
        discount_percent=discount,
        unit_price=unit_price,
        total=total,
    )


def check_discount(
    fields: ParsedFields, customer: CustomerRecord | None, price: PriceCheck
) -> DiscountCheck:
    """The customer's standard discount next to what the inquiry asks for; informational.

    A target price is compared with the standard unit price only when that price is known.
    """
    if customer is None:
        return DiscountCheck(status="skipped")
    standard = customer.standard_discount_percent
    requested = fields.price_value
    above = False
    if fields.price_kind == "discount_percent" and requested is not None:
        above = requested > standard
    elif (
        fields.price_kind == "target_price"
        and requested is not None
        and price.unit_price is not None
    ):
        above = requested < price.unit_price
    return DiscountCheck(
        status="above_standard" if above else "ok",
        standard_percent=standard,
        requested_kind=fields.price_kind,
        requested_value=requested,
    )


def check_credit(customer: CustomerRecord | None, price: PriceCheck) -> CreditCheck:
    """Balance plus the order value against the limit; informational."""
    if customer is None or price.total is None:
        return CreditCheck(status="skipped")
    status: CreditStatus
    if customer.credit_blocked:
        status = "blocked"
    elif customer.credit_balance + price.total > customer.credit_limit:
        status = "over_limit"
    else:
        status = "ok"
    return CreditCheck(
        status=status,
        limit=customer.credit_limit,
        balance=customer.credit_balance,
        order_value=price.total,
    )


def needs_input_reasons(
    fields: ParsedFields, customer: CustomerCheck, product: ProductRecord | None
) -> list[NeedsInputReason]:
    reasons: list[NeedsInputReason] = []
    if customer.status == "missing":
        reasons.append("customer_missing")
    elif customer.status == "not_found":
        reasons.append("customer_not_found")
    elif customer.status == "ambiguous":
        reasons.append("customer_ambiguous")
    if not (fields.product_code or "").strip():
        reasons.append("product_missing")
    elif product is None:
        reasons.append("product_not_found")
    if fields.quantity is None:
        reasons.append("quantity_missing")
    return reasons


def classify(
    fields: ParsedFields,
    product: ProductRecord | None,
    customer: CustomerCheck,
    stock: StockCheck,
    price: PriceCheck,
    discount: DiscountCheck,
    credit: CreditCheck,
) -> Classification:
    """Needs input first, then an exception for a missing quantity in stock, else standard.

    Discount and credit are shown but never change the outcome.
    """
    reasons = needs_input_reasons(fields, customer, product)
    results = CheckResults(
        customer=customer,
        stock=stock,
        price=price,
        discount=discount,
        credit=credit,
        reasons=reasons,
    )
    if reasons:
        return Classification(outcome="needs_input", exception_type=None, results=results)
    if stock.status == "insufficient":
        return Classification(
            outcome="exception", exception_type="insufficient_stock", results=results
        )
    return Classification(outcome="standard", exception_type=None, results=results)


def evaluate(
    fields: ParsedFields,
    sender_email: str,
    customers: Sequence[CustomerRecord],
    products: Sequence[ProductRecord],
) -> Classification:
    """All checks in order, without tracing steps."""
    customer_check, customer = match_customer(fields, sender_email, customers)
    product = find_product(fields, products)
    stock = check_stock(fields, product)
    price = check_price(fields, customer, product)
    discount = check_discount(fields, customer, price)
    credit = check_credit(customer, price)
    return classify(fields, product, customer_check, stock, price, discount, credit)
