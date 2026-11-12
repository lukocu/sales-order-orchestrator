"""The draft's offer and e-mail as pure functions: no database, no model, no clock.

The offer is the chosen recommendation option with the list prices of its products, or its
edit (unit price and quantity of the option's own lines), recomputed by code. The e-mail body
is assembled here from the offer's numbers; the drafter's paragraphs carry no digits.
"""

from collections import Counter, defaultdict, deque
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict

from app.checks.rules import CENT
from app.checks.schema import CheckResults
from app.draft.schema import DraftOffer, DraftText, OfferLine
from app.policy.rules import PolicyInputs, target_price_discount
from app.recommendation.options import margin_percent
from app.recommendation.schema import OptionLine, RecommendationOption

SIGNATURE = "Dział sprzedaży"


class LineEdit(BaseModel):
    """New quantity and unit price (PLN net) of one line of the option."""

    model_config = ConfigDict(extra="forbid")

    product_code: str
    quantity: int
    unit_price: Decimal


class InvalidEdit(ValueError):
    """The edit does not fit the option's lines or has a non-positive quantity or price."""


def _offer_line(line: OptionLine, list_prices: Mapping[str, Decimal]) -> OfferLine:
    return OfferLine(
        product_code=line.product_code,
        product_name=line.product_name,
        source=line.source,
        supplier=line.supplier,
        quantity=line.quantity,
        available_on=line.available_on,
        list_price=list_prices[line.product_code],
        unit_price=line.unit_price,
        unit_cost=line.unit_cost,
        value=line.value,
        cost=line.cost,
    )


def offer_from_option(
    option: RecommendationOption, list_prices: Mapping[str, Decimal]
) -> DraftOffer:
    """The option as recommended. `list_prices` must have every line's product code."""
    return DraftOffer(
        option_id=option.id,
        kind=option.kind,
        lines=[_offer_line(line, list_prices) for line in option.lines],
        covered_quantity=option.covered_quantity,
        requested_quantity=option.requested_quantity,
        fulfilled_on=option.fulfilled_on,
        meets_deadline=option.meets_deadline,
        value=option.value,
        cost=option.cost,
        margin_percent=option.margin_percent,
        edited=False,
    )


def _validate(edit: LineEdit) -> None:
    if edit.quantity < 1:
        raise InvalidEdit("Quantity must be at least 1")
    if edit.unit_price <= 0:
        raise InvalidEdit("Unit price must be above zero")
    if edit.unit_price != edit.unit_price.quantize(CENT):
        raise InvalidEdit("Unit price must have at most two decimal places")


def apply_edit(
    option: RecommendationOption,
    edits: Sequence[LineEdit],
    list_prices: Mapping[str, Decimal],
) -> DraftOffer:
    """The option with new quantities and unit prices of its lines, recomputed.

    The edits name exactly the option's lines by product code. When two lines share a code
    (own stock and a supplier of the same product), the edits of that code apply to them in
    the option's line order. Dates and the deadline stay those of the option.
    """
    if Counter(e.product_code for e in edits) != Counter(
        line.product_code for line in option.lines
    ):
        raise InvalidEdit("Edited lines must match the option's lines")
    by_code: defaultdict[str, deque[LineEdit]] = defaultdict(deque)
    for edit in edits:
        _validate(edit)
        by_code[edit.product_code].append(edit)

    lines: list[OfferLine] = []
    for line in option.lines:
        edit = by_code[line.product_code].popleft()
        lines.append(
            _offer_line(line, list_prices).model_copy(
                update={
                    "quantity": edit.quantity,
                    "unit_price": edit.unit_price,
                    "value": (edit.unit_price * edit.quantity).quantize(CENT, ROUND_HALF_UP),
                    "cost": (line.unit_cost * edit.quantity).quantize(CENT, ROUND_HALF_UP),
                }
            )
        )
    value = sum((line.value for line in lines), Decimal("0.00"))
    cost = sum((line.cost for line in lines), Decimal("0.00"))
    return DraftOffer(
        option_id=option.id,
        kind=option.kind,
        lines=lines,
        covered_quantity=sum(line.quantity for line in lines),
        requested_quantity=option.requested_quantity,
        fulfilled_on=option.fulfilled_on,
        meets_deadline=option.meets_deadline,
        value=value,
        cost=cost,
        margin_percent=margin_percent(value, cost),
        edited=True,
    )


def offered_discount(offer: DraftOffer) -> Decimal:
    """The largest discount of the offer's unit prices off their list prices, in percent."""
    return max(target_price_discount(line.unit_price, line.list_price) for line in offer.lines)


def offer_policy_inputs(offer: DraftOffer, checks: CheckResults) -> PolicyInputs:
    """Policy input of an offer: its value, margin and discount, with the customer's checks."""
    return PolicyInputs(
        option_id=offer.option_id,
        value=offer.value,
        margin_percent=offer.margin_percent,
        discount=checks.discount,
        list_price=checks.price.list_price,
        credit=checks.credit,
        offered_discount_percent=offered_discount(offer),
    )


# --- E-mail -----------------------------------------------------------------------------


def format_amount(amount: Decimal) -> str:
    """Polish format: a space between thousands and a decimal comma, e.g. 9 262,50."""
    return f"{amount.quantize(CENT, ROUND_HALF_UP):,.2f}".replace(",", " ").replace(".", ",")


def format_date(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def render_subject(inquiry_subject: str) -> str:
    subject = inquiry_subject.strip()
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def _line_text(line: OfferLine) -> str:
    return (
        f"- {line.product_name} ({line.product_code}): {line.quantity} szt. "
        f"× {format_amount(line.unit_price)} PLN netto = {format_amount(line.value)} PLN netto, "
        f"dostępne od {format_date(line.available_on)}"
    )


def render_body(offer: DraftOffer, text: DraftText, sender_name: str) -> str:
    """The e-mail body in Polish: every number comes from the offer, formatted here.

    `sender_name` is the inquiry's sender. It is not put into the greeting, which stays the
    neutral "Dzień dobry,": a Polish salutation with a name needs the vocative case.
    """
    return "\n".join(
        [
            "Dzień dobry,",
            "",
            text.intro,
            "",
            "Proponowane pozycje:",
            *(_line_text(line) for line in offer.lines),
            "",
            f"Razem: {format_amount(offer.value)} PLN netto.",
            f"Termin realizacji: {format_date(offer.fulfilled_on)}.",
            "",
            text.closing,
            "",
            "Z poważaniem",
            SIGNATURE,
        ]
    )
