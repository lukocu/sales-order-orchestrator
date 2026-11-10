"""Rule-based extractor: no key, no network. The default locally and in tests.

It reads the inquiry with a few regular expressions tuned to the demo inquiries; it is a
stand-in for the model, not a general parser.
"""

import datetime as dt
import re

from app.parsing.deadline import find_deadline_phrase, resolve_deadline
from app.parsing.extractor import ExtractionResult
from app.parsing.schema import ModelExtraction, PriceKind
from app.tracing.models import StepKind

_QUANTITY_AND_CODE = re.compile(r"(\d+)\s*szt\.?\s*([A-Z]{2,4}-\d{2,4})")
_NO_SUBSTITUTE = re.compile(
    r"nie\s+akceptujemy\s+zamiennik|wyłącznie\s+oryginaln|tylko\s+oryginaln|bez\s+zamiennik",
    re.IGNORECASE,
)
_SUBSTITUTE = re.compile(r"podobny\s+model|zamiennik", re.IGNORECASE)
_DISCOUNT = re.compile(r"rabat\w*\s+(\d{1,3}(?:[.,]\d+)?)\s*%", re.IGNORECASE)
_BEST_PRICE = re.compile(r"najlepsz\w*\s+cen\w*", re.IGNORECASE)


class RuleBasedExtractor:
    name = "fake"
    step_kind: StepKind = "deterministic"

    def extract(self, subject: str, body: str, reference_date: dt.date) -> ExtractionResult:
        quantity, product_code = _quantity_and_code(body, subject)
        deadline_text = find_deadline_phrase(body) or find_deadline_phrase(subject)
        deadline_date = None
        if deadline_text is not None:
            resolved = resolve_deadline(deadline_text, reference_date).date
            deadline_date = None if resolved is None else resolved.isoformat()
        price_kind, price_value, price_text = _price(body)
        extraction = ModelExtraction(
            customer=_customer(body),
            product_code=product_code,
            quantity=quantity,
            deadline_text=deadline_text,
            deadline_date=deadline_date,
            substitute_allowed=_substitute_allowed(body),
            price_kind=price_kind,
            price_value=price_value,
            price_text=price_text,
            uncertain=[],
        )
        return ExtractionResult(extraction=extraction, usage=None)


def _quantity_and_code(*texts: str) -> tuple[int | None, str | None]:
    for text in texts:
        match = _QUANTITY_AND_CODE.search(text)
        if match is not None:
            return int(match.group(1)), match.group(2)
    return None, None


def _substitute_allowed(body: str) -> bool | None:
    if _NO_SUBSTITUTE.search(body):
        return False
    if _SUBSTITUTE.search(body):
        return True
    return None


def _price(body: str) -> tuple[PriceKind, float | None, str | None]:
    discount = _DISCOUNT.search(body)
    if discount is not None:
        return "discount_percent", float(discount.group(1).replace(",", ".")), discount.group(0)
    best = _BEST_PRICE.search(body)
    if best is not None:
        return "best_price", None, best.group(0)
    return "none", None, None


def _customer(body: str) -> str | None:
    """Company from the signature: its last line, after a department ("Zakupy, ACME")."""
    lines = [line.strip() for line in body.strip().splitlines() if line.strip()]
    if not lines:
        return None
    return lines[-1].rsplit(",", 1)[-1].strip() or None
