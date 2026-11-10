"""Turn an extraction into validated fields plus a map of uncertain fields.

The rules live in code, not in the model: missing values, a deadline the rules and the model
read differently, an unresolvable phrase, or a price kind without a valid number. The model's
own uncertainty notes are appended per field. Bad model values never raise; they become
empty fields with a reason.
"""

import datetime as dt
import math
from collections.abc import Callable
from decimal import Decimal

from app.parsing.deadline import resolve_deadline
from app.parsing.schema import (
    MAX_TEXT_LENGTH,
    VALUED_PRICE_KINDS,
    FieldName,
    ModelExtraction,
    ParsedFields,
    PriceKind,
)

Uncertain = dict[FieldName, str]
_Flag = Callable[[FieldName, str], None]


def build_parsed(
    extraction: ModelExtraction, reference_date: dt.date
) -> tuple[ParsedFields, Uncertain]:
    reasons: dict[FieldName, list[str]] = {}

    def flag(field: FieldName, reason: str) -> None:
        reasons.setdefault(field, []).append(reason)

    customer = _text(extraction.customer, "customer", flag)
    product_code = _text(extraction.product_code, "product_code", flag)
    quantity = extraction.quantity
    if quantity is not None and quantity < 1:
        flag("quantity", f"Invalid quantity {quantity}")
        quantity = None
    missing: list[tuple[FieldName, object]] = [
        ("customer", customer),
        ("product_code", product_code),
        ("quantity", quantity),
    ]
    for field, value in missing:
        if value is None and field not in reasons:
            flag(field, "Missing")

    deadline_text = _text(extraction.deadline_text, "deadline", flag)
    deadline = _deadline(deadline_text, extraction.deadline_date, reference_date, flag)

    substitute_allowed = extraction.substitute_allowed
    if substitute_allowed is None:
        flag("substitute_allowed", "Not stated")

    price_text = _text(extraction.price_text, "price", flag)
    price_kind, price_value = _price(extraction.price_kind, extraction.price_value, flag)

    for item in extraction.uncertain:
        reason = item.reason.strip()[:MAX_TEXT_LENGTH]
        flag(item.field, f"Model: {reason}" if reason else "Model marked as uncertain")

    fields = ParsedFields(
        customer=customer,
        product_code=product_code,
        quantity=quantity,
        deadline=deadline,
        deadline_text=deadline_text,
        substitute_allowed=substitute_allowed,
        price_kind=price_kind,
        price_value=price_value,
        price_text=price_text,
    )
    return fields, {field: "; ".join(items) for field, items in reasons.items()}


def _text(value: str | None, field: FieldName, flag: _Flag) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_TEXT_LENGTH:
        flag(field, f"Text longer than {MAX_TEXT_LENGTH} characters, truncated")
        return stripped[:MAX_TEXT_LENGTH]
    return stripped


def _deadline(
    text: str | None, model_value: str | None, reference_date: dt.date, flag: _Flag
) -> dt.date | None:
    model_date = _iso_date(model_value)
    if text is None:
        if model_date is not None:
            flag("deadline", "Date given without the deadline phrase")
        return model_date
    resolution = resolve_deadline(text, reference_date)
    if resolution.date is not None:
        if model_date is not None and model_date != resolution.date:
            flag(
                "deadline",
                f"Rules read {resolution.date.isoformat()}, model read {model_date.isoformat()}",
            )
        if resolution.ambiguous:
            flag("deadline", "Ambiguous phrase")
        return resolution.date
    if model_date is not None:
        flag("deadline", "Resolved by model only")
        return model_date
    flag("deadline", "Could not resolve the deadline phrase")
    return None


def _iso_date(value: str | None) -> dt.date | None:
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        return None


def _price(kind: PriceKind, value: float | None, flag: _Flag) -> tuple[PriceKind, Decimal | None]:
    if kind not in VALUED_PRICE_KINDS:
        return kind, None
    if value is None or not math.isfinite(value):
        flag("price", f"No number given for {kind}")
        return "none", None
    number = Decimal(str(value))
    in_range = 0 < number <= 100 if kind == "discount_percent" else number > 0
    if not in_range:
        flag("price", f"Value {number} out of range for {kind}")
        return "none", None
    return kind, number
