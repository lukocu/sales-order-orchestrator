"""The four specialised agents: deterministic, read-only, no model.

Each agent reads its tables in one short session and computes its result with a pure
function, so a rule can be tested without a database. Agents never write: retrying one is
safe.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.checks.models import Product
from app.orchestration.models import CustomerOrder, ProductSubstitute, SupplierOffer
from app.orchestration.schema import (
    AgentResult,
    Capability,
    Compatibility,
    CustomerHistoryResult,
    HistorySignal,
    SubstituteAvailabilityResult,
    SubstituteCandidate,
    SubstituteCompatibilityResult,
    SubstituteConsent,
    SubstituteStock,
    SupplierAvailabilityResult,
    SupplierDelivery,
)


@dataclass(frozen=True)
class AgentInput:
    """What every agent gets; `upstream` holds the results of the task's prerequisites."""

    customer_id: int
    product_id: int
    product_code: str
    requested: int
    shortage: int
    deadline: date | None
    reference_date: date  # supplier lead times are counted from it
    consent: SubstituteConsent
    upstream: Mapping[Capability, AgentResult] = field(default_factory=dict)


class MissingUpstream(Exception):
    """A prerequisite's result is not in `AgentInput.upstream`."""


@dataclass(frozen=True)
class SubstituteRecord:
    code: str
    name: str
    compatibility: Compatibility
    note: str


@dataclass(frozen=True)
class OfferRecord:
    supplier_name: str
    quantity: int
    lead_time_days: int


@dataclass(frozen=True)
class OrderRecord:
    substitute_offered: bool
    substitute_accepted: bool | None


# --- Pure rules -------------------------------------------------------------------------


def rank_substitutes(rows: Sequence[SubstituteRecord]) -> SubstituteCompatibilityResult:
    """Candidates with full compatibility first, then by code."""
    ranked = sorted(rows, key=lambda r: (r.compatibility != "full", r.code))
    return SubstituteCompatibilityResult(
        candidates=[
            SubstituteCandidate(
                code=r.code, name=r.name, compatibility=r.compatibility, note=r.note
            )
            for r in ranked
        ]
    )


def substitute_stock(
    compatibility: SubstituteCompatibilityResult,
    stock_by_code: Mapping[str, int],
    shortage: int,
) -> SubstituteAvailabilityResult:
    """Stock of each candidate, in the upstream order; a missing product counts as 0."""
    candidates = []
    for candidate in compatibility.candidates:
        stock = stock_by_code.get(candidate.code, 0)
        candidates.append(
            SubstituteStock(code=candidate.code, stock=stock, covers_shortage=stock >= shortage)
        )
    return SubstituteAvailabilityResult(candidates=candidates)


def supplier_deliveries(
    offers: Sequence[OfferRecord],
    *,
    reference_date: date,
    deadline: date | None,
    shortage: int,
) -> SupplierAvailabilityResult:
    """Delivery date of each offer (earliest first) and whether it meets the deadline."""
    deliveries = []
    for offer in sorted(offers, key=lambda o: (o.lead_time_days, o.supplier_name)):
        available_on = reference_date + timedelta(days=offer.lead_time_days)
        deliveries.append(
            SupplierDelivery(
                supplier=offer.supplier_name,
                quantity=offer.quantity,
                lead_time_days=offer.lead_time_days,
                available_on=available_on,
                meets_deadline=None if deadline is None else available_on <= deadline,
                covers_shortage=offer.quantity >= shortage,
            )
        )
    return SupplierAvailabilityResult(offers=deliveries)


def history_signal(offered: int, accepted: int) -> HistorySignal:
    if offered == 0:
        return "no_substitute_history"
    if accepted == offered:
        return "accepted_before"
    if accepted == 0:
        return "declined_before"
    return "mixed"


def customer_history(orders: Sequence[OrderRecord]) -> CustomerHistoryResult:
    offered = sum(1 for o in orders if o.substitute_offered)
    accepted = sum(1 for o in orders if o.substitute_offered and o.substitute_accepted)
    return CustomerHistoryResult(
        orders_count=len(orders),
        substitutes_offered=offered,
        substitutes_accepted=accepted,
        signal=history_signal(offered, accepted),
    )


# --- Agents (read in a short session, then compute) ------------------------------------


def run_catalog_agent(engine: Engine, agent_input: AgentInput) -> SubstituteCompatibilityResult:
    with Session(engine) as session:
        rows = session.exec(
            select(ProductSubstitute, Product)
            .join(Product, col(Product.id) == col(ProductSubstitute.substitute_product_id))
            .where(col(ProductSubstitute.product_id) == agent_input.product_id)
        ).all()
        records = [
            SubstituteRecord(
                code=product.code,
                name=product.name,
                compatibility=substitute.compatibility,
                note=substitute.note,
            )
            for substitute, product in rows
        ]
    return rank_substitutes(records)


def run_warehouse_agent(engine: Engine, agent_input: AgentInput) -> SubstituteAvailabilityResult:
    compatibility = agent_input.upstream.get("substitute-compatibility")
    if not isinstance(compatibility, SubstituteCompatibilityResult):
        raise MissingUpstream("substitute-availability needs a substitute-compatibility result")
    codes = [c.code for c in compatibility.candidates]
    stock_by_code: dict[str, int] = {}
    if codes:
        with Session(engine) as session:
            rows = session.exec(
                select(Product.code, Product.stock_quantity).where(col(Product.code).in_(codes))
            ).all()
        stock_by_code = dict(rows)
    return substitute_stock(compatibility, stock_by_code, agent_input.shortage)


def run_supplier_agent(engine: Engine, agent_input: AgentInput) -> SupplierAvailabilityResult:
    with Session(engine) as session:
        rows = session.exec(
            select(SupplierOffer).where(col(SupplierOffer.product_id) == agent_input.product_id)
        ).all()
        offers = [
            OfferRecord(
                supplier_name=o.supplier_name, quantity=o.quantity, lead_time_days=o.lead_time_days
            )
            for o in rows
        ]
    return supplier_deliveries(
        offers,
        reference_date=agent_input.reference_date,
        deadline=agent_input.deadline,
        shortage=agent_input.shortage,
    )


def run_history_agent(engine: Engine, agent_input: AgentInput) -> CustomerHistoryResult:
    with Session(engine) as session:
        rows = session.exec(
            select(CustomerOrder.substitute_offered, CustomerOrder.substitute_accepted).where(
                col(CustomerOrder.customer_id) == agent_input.customer_id
            )
        ).all()
    return customer_history(
        [OrderRecord(substitute_offered=o, substitute_accepted=a) for o, a in rows]
    )
