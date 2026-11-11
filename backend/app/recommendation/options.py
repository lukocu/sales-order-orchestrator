"""Options of fulfilling an inquiry with a stock exception, priced, with confidence.

Pure functions: no database, no model, no clock. Every option starts from the requested
product's own stock and takes the shortage from a substitute, a supplier, or both. Substitutes
and suppliers come only from completed orchestration tasks, so an option's coverage and date
are always known; a missing task is a risk of the option, not a blocker.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from app.checks.rules import CENT, HUNDRED
from app.orchestration.schema import (
    Capability,
    CustomerHistoryResult,
    SubstituteAvailabilityResult,
    SubstituteCompatibilityResult,
    SubstituteConsent,
    SupplierAvailabilityResult,
    SupplierDelivery,
    TaskOutcome,
    TaskStatus,
)
from app.recommendation.confidence import ConfidenceContext, assess
from app.recommendation.schema import (
    LineSource,
    OptionKind,
    OptionLine,
    RecommendationFacts,
    RecommendationOption,
)

STOCK_ID = "stock"


@dataclass(frozen=True)
class PricedProduct:
    code: str
    name: str
    list_price: Decimal
    unit_cost: Decimal  # cost of own stock


@dataclass(frozen=True)
class RecommendationInputs:
    product: PricedProduct  # the requested product
    requested: int
    available: int
    shortage: int
    deadline: date | None
    reference_date: date  # own stock is available on this date
    consent: SubstituteConsent
    discount_percent: Decimal  # the customer's standard discount
    products_by_code: Mapping[str, PricedProduct]  # substitutes
    supplier_costs: Mapping[tuple[str, str], Decimal]  # (supplier, product code) -> unit cost
    tasks: Sequence[TaskOutcome]  # of the orchestration result
    uncertain_inputs: Sequence[str] = ()  # uncertain analysis fields the checks used


def _completed[R: BaseModel](tasks: Sequence[TaskOutcome], result_type: type[R]) -> R | None:
    for task in tasks:
        if task.status == "completed" and isinstance(task.result, result_type):
            return task.result
    return None


def confidence_context(inputs: RecommendationInputs) -> ConfidenceContext:
    compatibility = _completed(inputs.tasks, SubstituteCompatibilityResult)
    history = _completed(inputs.tasks, CustomerHistoryResult)
    statuses: dict[Capability, TaskStatus] = {t.capability: t.status for t in inputs.tasks}
    return ConfidenceContext(
        deadline=inputs.deadline,
        consent=inputs.consent,
        task_statuses=statuses,
        compatibility=(
            {}
            if compatibility is None
            else {c.code: c.compatibility for c in compatibility.candidates}
        ),
        history=None if history is None else history.signal,
        uncertain_inputs=list(inputs.uncertain_inputs),
    )


def recommendation_facts(inputs: RecommendationInputs) -> RecommendationFacts:
    return RecommendationFacts(
        product_code=inputs.product.code,
        product_name=inputs.product.name,
        requested=inputs.requested,
        available=inputs.available,
        shortage=inputs.shortage,
        deadline=inputs.deadline,
        reference_date=inputs.reference_date,
        substitute_consent=inputs.consent,
        discount_percent=inputs.discount_percent,
        uncertain_inputs=list(inputs.uncertain_inputs),
    )


def unit_price(list_price: Decimal, discount_percent: Decimal) -> Decimal:
    return (list_price * (HUNDRED - discount_percent) / HUNDRED).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def margin_percent(value: Decimal, cost: Decimal) -> Decimal:
    """(value - cost) / value in percent; 0 for a zero value (a 100% discount)."""
    if value == 0:
        return Decimal("0.00")
    return ((value - cost) / value * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)


def _line(
    product: PricedProduct,
    *,
    source: LineSource,
    quantity: int,
    available_on: date,
    unit_cost: Decimal,
    discount_percent: Decimal,
    supplier: str | None = None,
) -> OptionLine:
    price = unit_price(product.list_price, discount_percent)
    return OptionLine(
        product_code=product.code,
        product_name=product.name,
        source=source,
        supplier=supplier,
        quantity=quantity,
        available_on=available_on,
        unit_price=price,
        unit_cost=unit_cost,
        value=(price * quantity).quantize(CENT, rounding=ROUND_HALF_UP),
        cost=(unit_cost * quantity).quantize(CENT, rounding=ROUND_HALF_UP),
    )


def _option(
    option_id: str,
    kind: OptionKind,
    lines: list[OptionLine],
    inputs: RecommendationInputs,
    context: ConfidenceContext,
) -> RecommendationOption:
    fulfilled_on = max(line.available_on for line in lines)
    value = sum((line.value for line in lines), Decimal("0.00"))
    cost = sum((line.cost for line in lines), Decimal("0.00"))
    option = RecommendationOption(
        id=option_id,
        kind=kind,
        lines=lines,
        covered_quantity=sum(line.quantity for line in lines),
        requested_quantity=inputs.requested,
        fulfilled_on=fulfilled_on,
        meets_deadline=None if inputs.deadline is None else fulfilled_on <= inputs.deadline,
        value=value,
        cost=cost,
        margin_percent=margin_percent(value, cost),
        band="LOW",  # replaced below
        signals=[],
    )
    band, signals = assess(option, context)
    return option.model_copy(update={"band": band, "signals": signals})


@dataclass(frozen=True)
class _Substitute:
    product: PricedProduct
    stock: int


@dataclass(frozen=True)
class _Offer:
    delivery: SupplierDelivery
    unit_cost: Decimal


def _substitutes(inputs: RecommendationInputs) -> list[_Substitute]:
    """Substitutes with stock, from completed compatibility and availability tasks only."""
    if inputs.consent == "refused":
        return []
    compatibility = _completed(inputs.tasks, SubstituteCompatibilityResult)
    availability = _completed(inputs.tasks, SubstituteAvailabilityResult)
    if compatibility is None or availability is None:
        return []
    compatible = {c.code for c in compatibility.candidates}
    result: list[_Substitute] = []
    for candidate in availability.candidates:
        product = inputs.products_by_code.get(candidate.code)
        if candidate.stock > 0 and candidate.code in compatible and product is not None:
            result.append(_Substitute(product=product, stock=candidate.stock))
    return result


def _offers(inputs: RecommendationInputs) -> list[_Offer]:
    """Supplier offers with a known cost, from a completed supplier task only."""
    supplier = _completed(inputs.tasks, SupplierAvailabilityResult)
    if supplier is None:
        return []
    result: list[_Offer] = []
    for delivery in supplier.offers:
        cost = inputs.supplier_costs.get((delivery.supplier, inputs.product.code))
        if delivery.quantity > 0 and cost is not None:
            result.append(_Offer(delivery=delivery, unit_cost=cost))
    return result


def build_options(inputs: RecommendationInputs) -> list[RecommendationOption]:
    """All options in build order: stock, stock+substitute, stock+supplier, combined.

    Without own stock there is no `stock` option and the other options have no stock line
    (their id then has no `stock+` prefix).
    """
    context = confidence_context(inputs)
    discount = inputs.discount_percent
    product = inputs.product
    stock_quantity = max(min(inputs.available, inputs.requested), 0)
    missing = inputs.requested - stock_quantity

    stock_lines: list[OptionLine] = []
    if stock_quantity > 0:
        stock_lines.append(
            _line(
                product,
                source="stock",
                quantity=stock_quantity,
                available_on=inputs.reference_date,
                unit_cost=product.unit_cost,
                discount_percent=discount,
            )
        )
    prefix = f"{STOCK_ID}+" if stock_lines else ""

    def substitute_line(substitute: _Substitute, quantity: int) -> OptionLine:
        return _line(
            substitute.product,
            source="substitute_stock",
            quantity=quantity,
            available_on=inputs.reference_date,
            unit_cost=substitute.product.unit_cost,
            discount_percent=discount,
        )

    def supplier_line(offer: _Offer, quantity: int) -> OptionLine:
        return _line(
            product,
            source="supplier",
            supplier=offer.delivery.supplier,
            quantity=quantity,
            available_on=offer.delivery.available_on,
            unit_cost=offer.unit_cost,
            discount_percent=discount,
        )

    options: list[RecommendationOption] = []
    if stock_lines:
        options.append(_option(STOCK_ID, "partial_delivery", stock_lines, inputs, context))
    if missing <= 0:
        return options

    substitutes = _substitutes(inputs)
    offers = _offers(inputs)
    for substitute in substitutes:
        lines = [*stock_lines, substitute_line(substitute, min(missing, substitute.stock))]
        options.append(
            _option(f"{prefix}{substitute.product.code}", "substitute", lines, inputs, context)
        )
    for offer in offers:
        lines = [*stock_lines, supplier_line(offer, min(missing, offer.delivery.quantity))]
        supplier_id = f"supplier:{offer.delivery.supplier}"
        options.append(_option(f"{prefix}{supplier_id}", "other_source", lines, inputs, context))
    for substitute in substitutes:
        for offer in offers:
            if substitute.stock >= missing or offer.delivery.quantity >= missing:
                continue  # one of them covers the shortage alone
            rest = missing - substitute.stock
            lines = [
                *stock_lines,
                substitute_line(substitute, substitute.stock),
                supplier_line(offer, min(rest, offer.delivery.quantity)),
            ]
            option_id = f"{prefix}{substitute.product.code}+supplier:{offer.delivery.supplier}"
            options.append(_option(option_id, "combined", lines, inputs, context))
    return options
