from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, col, select

from app.checks.models import Customer, Product
from app.checks.rules import CustomerRecord, ProductRecord, evaluate
from app.inquiries.models import Inquiry
from app.orchestration.models import (
    CustomerOrder,
    InquiryOrchestration,
    ProductSubstitute,
    SupplierOffer,
)
from tests.conftest import InquiryFactory
from tests.test_checks_rules import SEED_CUSTOMERS, SEED_PRODUCTS, _seed_fields
from tests.test_parsing_extractors import ACME, BIURO_MAX, DELTA, OMEGA

# The orchestration seed (migrations/versions/0007_orchestration_data.py).
NEW_PRODUCTS = (
    ("ABC-110", "Czujnik ciśnienia ABC-110", Decimal("125.00"), 40),
    ("XYZ-310", "Zawór proporcjonalny XYZ-310", Decimal("250.00"), 100),
)
SUBSTITUTES = {("ABC-100", "ABC-110", "full"), ("XYZ-300", "XYZ-310", "partial")}
SUPPLIER_OFFERS = {("ABC-100", 200, 7), ("XYZ-300", 80, 5)}
# customer -> sorted (substitute_offered, substitute_accepted) of each order
ORDER_HISTORY = {
    "ACME": [(False, None), (True, True)],
    "Hurtownia Delta": [(False, None)],
    "Technika Omega": [(True, False)],
    "Biuro Max": [],
}
SEED_INQUIRIES = (
    (ACME, "zakupy@acme.example"),
    (BIURO_MAX, "biuro@biuromax.example"),
    (DELTA, "handel@hurtowniadelta.example"),
    (OMEGA, "zaopatrzenie@technikaomega.example"),
)


def _product_ids(engine: Engine) -> dict[str, int]:
    with Session(engine) as session:
        rows = session.exec(select(Product.code, Product.id)).all()
    return {code: product_id for code, product_id in rows if product_id is not None}


def _customer_id(engine: Engine, name: str) -> int:
    with Session(engine) as session:
        customer_id = session.exec(select(Customer.id).where(col(Customer.name) == name)).one()
    assert customer_id is not None
    return customer_id


def _assert_rejected(engine: Engine, row: SQLModel, constraint: str) -> None:
    with Session(engine) as session, pytest.raises(IntegrityError, match=constraint):
        session.add(row)
        session.commit()


def _orchestration(inquiry: Inquiry, **overrides: object) -> InquiryOrchestration:
    assert inquiry.id is not None
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "inquiry_id": inquiry.id,
        "analysis_version": now,
        "checks_checked_at": now,
        "status": "failed",
        "result": {"status": "failed"},
        "orchestrated_at": now,
    }
    values.update(overrides)
    return InquiryOrchestration.model_validate(values)


# --- Seed -----------------------------------------------------------------------------


def test_seed_adds_substitute_products(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        by_code = {p.code: p for p in session.exec(select(Product)).all()}

    for code, name, list_price, stock_quantity in NEW_PRODUCTS:
        stored = by_code[code]
        assert (stored.name, stored.list_price, stored.stock_quantity) == (
            name,
            list_price,
            stock_quantity,
        )


def test_seed_matches_agent_data(migrated_engine: Engine) -> None:
    codes = {product_id: code for code, product_id in _product_ids(migrated_engine).items()}
    with Session(migrated_engine) as session:
        substitutes = session.exec(select(ProductSubstitute)).all()
        offers = session.exec(select(SupplierOffer)).all()
        orders = session.exec(select(CustomerOrder, Customer.name).join(Customer)).all()
        customer_names = session.exec(select(Customer.name)).all()

    assert {
        (codes[s.product_id], codes[s.substitute_product_id], s.compatibility) for s in substitutes
    } == SUBSTITUTES
    assert all(s.note for s in substitutes)
    assert {(codes[o.product_id], o.quantity, o.lead_time_days) for o in offers} == (
        SUPPLIER_OFFERS
    )
    history: dict[str, list[tuple[bool, bool | None]]] = {name: [] for name in customer_names}
    for order, name in orders:
        history[name].append((order.substitute_offered, order.substitute_accepted))
    assert {
        name: sorted(entries, key=lambda e: (e[0], e[1] is True))
        for name, entries in history.items()
    } == ORDER_HISTORY


def test_new_products_keep_seed_check_results(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        customers = [
            CustomerRecord(
                id=c.id or 0,
                name=c.name,
                email_domain=c.email_domain,
                standard_discount_percent=c.standard_discount_percent,
                credit_limit=c.credit_limit,
                credit_balance=c.credit_balance,
                credit_blocked=c.credit_blocked,
            )
            for c in session.exec(select(Customer)).all()
        ]
        products = [
            ProductRecord(
                id=p.id or 0,
                code=p.code,
                name=p.name,
                list_price=p.list_price,
                stock_quantity=p.stock_quantity,
            )
            for p in session.exec(select(Product)).all()
        ]
    assert {code for code, *_ in NEW_PRODUCTS} <= {p.code for p in products}

    for inquiry, sender in SEED_INQUIRIES:
        fields = _seed_fields(inquiry)
        before = evaluate(fields, sender, SEED_CUSTOMERS, SEED_PRODUCTS)
        after = evaluate(fields, sender, customers, products)

        assert (after.outcome, after.exception_type) == (before.outcome, before.exception_type)
        assert after.results.stock == before.results.stock
        assert after.results.price == before.results.price
        assert after.results.discount == before.results.discount
        assert after.results.credit == before.results.credit
        assert after.results.reasons == before.results.reasons


# --- Constraints ----------------------------------------------------------------------


def test_substitute_cannot_be_the_product_itself(migrated_engine: Engine) -> None:
    product_id = _product_ids(migrated_engine)["ABC-200"]
    row = ProductSubstitute(
        product_id=product_id, substitute_product_id=product_id, compatibility="full", note="x"
    )

    _assert_rejected(migrated_engine, row, "ck_product_substitutes_not_self")


def test_substitute_compatibility_rejects_unknown_value(migrated_engine: Engine) -> None:
    ids = _product_ids(migrated_engine)
    row = ProductSubstitute(
        product_id=ids["ABC-200"],
        substitute_product_id=ids["ABC-100"],
        compatibility="none",  # type: ignore[arg-type]
        note="x",
    )

    _assert_rejected(migrated_engine, row, "ck_product_substitutes_compatibility")


def test_substitute_pair_is_unique(migrated_engine: Engine) -> None:
    ids = _product_ids(migrated_engine)
    row = ProductSubstitute(
        product_id=ids["ABC-100"],
        substitute_product_id=ids["ABC-110"],
        compatibility="partial",
        note="x",
    )

    _assert_rejected(
        migrated_engine, row, "uq_product_substitutes_product_id_substitute_product_id"
    )


@pytest.mark.parametrize(
    ("quantity", "lead_time_days", "constraint"),
    [
        (0, 3, "ck_supplier_offers_quantity"),
        (10, -1, "ck_supplier_offers_lead_time_days"),
    ],
)
def test_supplier_offer_checks(
    migrated_engine: Engine, quantity: int, lead_time_days: int, constraint: str
) -> None:
    row = SupplierOffer(
        product_id=_product_ids(migrated_engine)["ABC-200"],
        supplier_name="Test",
        quantity=quantity,
        lead_time_days=lead_time_days,
    )

    _assert_rejected(migrated_engine, row, constraint)


@pytest.mark.parametrize(
    ("quantity", "offered", "accepted", "constraint"),
    [
        (0, False, None, "ck_customer_orders_quantity"),
        (5, False, True, "ck_customer_orders_substitute_accepted_with_offered"),
        (5, True, None, "ck_customer_orders_substitute_accepted_with_offered"),
    ],
)
def test_customer_order_checks(
    migrated_engine: Engine,
    quantity: int,
    offered: bool,
    accepted: bool | None,
    constraint: str,
) -> None:
    row = CustomerOrder(
        customer_id=_customer_id(migrated_engine, "Biuro Max"),
        product_id=_product_ids(migrated_engine)["ABC-200"],
        quantity=quantity,
        ordered_on=date(2026, 10, 1),
        substitute_offered=offered,
        substitute_accepted=accepted,
    )

    _assert_rejected(migrated_engine, row, constraint)


def test_orchestration_status_rejects_unknown_value(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    row = _orchestration(make_inquiry(received_at=datetime.now(UTC)))
    row.status = "running"  # type: ignore[assignment]

    _assert_rejected(migrated_engine, row, "ck_inquiry_orchestrations_status")


def test_one_orchestration_per_inquiry(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    with Session(migrated_engine) as session:
        session.add(_orchestration(inquiry))
        session.commit()

    _assert_rejected(
        migrated_engine, _orchestration(inquiry), "uq_inquiry_orchestrations_inquiry_id"
    )


def test_deleting_inquiry_deletes_orchestration(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    with Session(migrated_engine) as session:
        session.add(_orchestration(inquiry, status="completed", result={"tasks": []}))
        session.commit()

    with Session(migrated_engine) as session:
        session.delete(session.get_one(Inquiry, inquiry.id))
        session.commit()
        remaining = session.exec(
            select(InquiryOrchestration).where(col(InquiryOrchestration.inquiry_id) == inquiry.id)
        ).all()

    assert remaining == []
