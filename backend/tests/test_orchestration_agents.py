from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.checks.models import Customer, Product
from app.orchestration.agents import (
    AgentInput,
    MissingUpstream,
    OfferRecord,
    OrderRecord,
    SubstituteRecord,
    customer_history,
    history_signal,
    rank_substitutes,
    run_catalog_agent,
    run_history_agent,
    run_supplier_agent,
    run_warehouse_agent,
    substitute_stock,
    supplier_deliveries,
)
from app.orchestration.planning import substitute_consent
from app.orchestration.schema import (
    HistorySignal,
    SubstituteCandidate,
    SubstituteCompatibilityResult,
    SubstituteStock,
    SupplierDelivery,
)
from tests.test_checks_rules import _seed_fields
from tests.test_parsing_extractors import ACME, DELTA, OMEGA

REFERENCE = date(2026, 11, 2)


def _candidates(*codes: str) -> SubstituteCompatibilityResult:
    return SubstituteCompatibilityResult(
        candidates=[
            SubstituteCandidate(code=c, name=c, compatibility="full", note="n") for c in codes
        ]
    )


# --- Pure rules -------------------------------------------------------------------------


def test_substitutes_rank_full_first_then_by_code() -> None:
    result = rank_substitutes(
        [
            SubstituteRecord("ABC-130", "C", "partial", "n"),
            SubstituteRecord("ABC-120", "B", "full", "n"),
            SubstituteRecord("ABC-110", "A", "partial", "n"),
            SubstituteRecord("ABC-140", "D", "full", "n"),
        ]
    )

    assert [(c.code, c.compatibility) for c in result.candidates] == [
        ("ABC-120", "full"),
        ("ABC-140", "full"),
        ("ABC-110", "partial"),
        ("ABC-130", "partial"),
    ]


@pytest.mark.parametrize(("stock", "covers"), [(29, False), (30, True), (31, True)])
def test_substitute_stock_equal_to_shortage_covers_it(stock: int, covers: bool) -> None:
    result = substitute_stock(_candidates("ABC-110"), {"ABC-110": stock}, shortage=30)

    assert result.candidates == [
        SubstituteStock(code="ABC-110", stock=stock, covers_shortage=covers)
    ]


def test_substitute_stock_keeps_upstream_order_and_defaults_to_zero() -> None:
    result = substitute_stock(_candidates("B", "A"), {"A": 5}, shortage=1)

    assert [(c.code, c.stock, c.covers_shortage) for c in result.candidates] == [
        ("B", 0, False),
        ("A", 5, True),
    ]


@pytest.mark.parametrize(("quantity", "covers"), [(29, False), (30, True)])
def test_supplier_quantity_equal_to_shortage_covers_it(quantity: int, covers: bool) -> None:
    result = supplier_deliveries(
        [OfferRecord("S", quantity, 0)], reference_date=REFERENCE, deadline=None, shortage=30
    )

    assert result.offers[0].covers_shortage is covers


@pytest.mark.parametrize(("lead_time_days", "meets"), [(3, True), (4, True), (5, False)])
def test_supplier_delivery_on_the_deadline_meets_it(lead_time_days: int, meets: bool) -> None:
    result = supplier_deliveries(
        [OfferRecord("S", 10, lead_time_days)],
        reference_date=REFERENCE,
        deadline=date(2026, 11, 6),
        shortage=10,
    )

    [offer] = result.offers
    assert offer.available_on == date(2026, 11, 2 + lead_time_days)
    assert offer.meets_deadline is meets


def test_supplier_without_deadline_has_no_verdict_and_earliest_comes_first() -> None:
    result = supplier_deliveries(
        [OfferRecord("Late", 10, 9), OfferRecord("Early", 10, 2)],
        reference_date=REFERENCE,
        deadline=None,
        shortage=10,
    )

    assert [(o.supplier, o.meets_deadline) for o in result.offers] == [
        ("Early", None),
        ("Late", None),
    ]


@pytest.mark.parametrize(
    ("offered", "accepted", "signal"),
    [
        (0, 0, "no_substitute_history"),
        (1, 1, "accepted_before"),
        (2, 2, "accepted_before"),
        (1, 0, "declined_before"),
        (3, 0, "declined_before"),
        (2, 1, "mixed"),
    ],
)
def test_history_signal(offered: int, accepted: int, signal: HistorySignal) -> None:
    assert history_signal(offered, accepted) == signal


def test_customer_history_counts_orders() -> None:
    result = customer_history(
        [
            OrderRecord(substitute_offered=False, substitute_accepted=None),
            OrderRecord(substitute_offered=True, substitute_accepted=True),
            OrderRecord(substitute_offered=True, substitute_accepted=False),
        ]
    )

    assert (
        result.orders_count,
        result.substitutes_offered,
        result.substitutes_accepted,
        result.signal,
    ) == (3, 2, 1, "mixed")


def test_customer_without_orders_has_no_history() -> None:
    result = customer_history([])

    assert (result.orders_count, result.signal) == (0, "no_substitute_history")


# --- Agents on the seed -----------------------------------------------------------------


def _seed_input(
    engine: Engine,
    inquiry: tuple[str, str, date],
    customer: str,
    *,
    requested: int,
    shortage: int,
) -> AgentInput:
    fields = _seed_fields(inquiry)
    assert fields.product_code is not None
    with Session(engine) as session:
        product = session.exec(
            select(Product).where(col(Product.code) == fields.product_code)
        ).one()
        customer_id = session.exec(select(Customer.id).where(col(Customer.name) == customer)).one()
    assert product.id is not None
    assert customer_id is not None
    assert fields.quantity == requested
    return AgentInput(
        customer_id=customer_id,
        product_id=product.id,
        product_code=product.code,
        requested=requested,
        shortage=shortage,
        deadline=fields.deadline,
        reference_date=inquiry[2],
        consent=substitute_consent(fields.substitute_allowed),
    )


def test_seed_acme(migrated_engine: Engine) -> None:
    agent_input = _seed_input(migrated_engine, ACME, "ACME", requested=80, shortage=30)
    assert (agent_input.deadline, agent_input.consent) == (date(2026, 11, 6), "confirmed")

    compatibility = run_catalog_agent(migrated_engine, agent_input)
    availability = run_warehouse_agent(
        migrated_engine,
        replace(agent_input, upstream={"substitute-compatibility": compatibility}),
    )
    supplier = run_supplier_agent(migrated_engine, agent_input)
    history = run_history_agent(migrated_engine, agent_input)

    assert [(c.code, c.compatibility) for c in compatibility.candidates] == [("ABC-110", "full")]
    assert compatibility.candidates[0].name == "Czujnik ciśnienia ABC-110"
    assert compatibility.candidates[0].note
    assert availability.candidates == [
        SubstituteStock(code="ABC-110", stock=40, covers_shortage=True)
    ]
    assert supplier.offers == [
        SupplierDelivery(
            supplier="Sensortech Polska",
            quantity=200,
            lead_time_days=7,
            available_on=date(2026, 11, 9),
            meets_deadline=False,
            covers_shortage=True,
        )
    ]
    assert (
        history.orders_count,
        history.substitutes_offered,
        history.substitutes_accepted,
        history.signal,
    ) == (2, 1, 1, "accepted_before")


def test_seed_omega(migrated_engine: Engine) -> None:
    agent_input = _seed_input(migrated_engine, OMEGA, "Technika Omega", requested=120, shortage=60)
    assert (agent_input.deadline, agent_input.consent) == (date(2026, 11, 12), "refused")

    supplier = run_supplier_agent(migrated_engine, agent_input)
    history = run_history_agent(migrated_engine, agent_input)
    compatibility = run_catalog_agent(migrated_engine, agent_input)

    assert supplier.offers == [
        SupplierDelivery(
            supplier="Hydro-Valve",
            quantity=80,
            lead_time_days=5,
            available_on=date(2026, 11, 10),
            meets_deadline=True,
            covers_shortage=True,
        )
    ]
    assert (
        history.orders_count,
        history.substitutes_offered,
        history.substitutes_accepted,
        history.signal,
    ) == (1, 1, 0, "declined_before")
    # Not planned for Omega (substitutes refused), but the catalogue knows a partial one.
    assert [(c.code, c.compatibility) for c in compatibility.candidates] == [("XYZ-310", "partial")]


def test_seed_delta(migrated_engine: Engine) -> None:
    agent_input = _seed_input(
        migrated_engine, DELTA, "Hurtownia Delta", requested=500, shortage=450
    )
    assert (agent_input.deadline, agent_input.consent) == (None, "unconfirmed")

    compatibility = run_catalog_agent(migrated_engine, agent_input)
    availability = run_warehouse_agent(
        migrated_engine,
        replace(agent_input, upstream={"substitute-compatibility": compatibility}),
    )
    supplier = run_supplier_agent(migrated_engine, agent_input)
    history = run_history_agent(migrated_engine, agent_input)

    assert [c.code for c in compatibility.candidates] == ["ABC-110"]
    assert availability.candidates == [
        SubstituteStock(code="ABC-110", stock=40, covers_shortage=False)
    ]
    [offer] = supplier.offers
    assert (offer.quantity, offer.meets_deadline, offer.covers_shortage) == (200, None, False)
    assert offer.available_on == date(2026, 11, 11)
    assert (history.orders_count, history.substitutes_offered, history.signal) == (
        1,
        0,
        "no_substitute_history",
    )


def test_warehouse_agent_needs_upstream(migrated_engine: Engine) -> None:
    agent_input = _seed_input(migrated_engine, ACME, "ACME", requested=80, shortage=30)

    with pytest.raises(MissingUpstream):
        run_warehouse_agent(migrated_engine, agent_input)
