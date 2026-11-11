from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, col, select

from app.checks.models import Product
from app.inquiries.models import Inquiry
from app.orchestration.models import SupplierOffer
from app.recommendation.models import InquiryRecommendation
from tests.conftest import InquiryFactory

# The cost seed (migrations/versions/0009_recommendation_data.py).
PRODUCT_COSTS = {
    "ABC-100": Decimal("84.00"),
    "ABC-110": Decimal("90.00"),
    "ABC-200": Decimal("60.00"),
    "XYZ-300": Decimal("170.00"),
    "XYZ-310": Decimal("180.00"),
}
OFFER_COSTS = {
    ("Sensortech Polska", "ABC-100"): Decimal("96.00"),
    ("Hydro-Valve", "XYZ-300"): Decimal("185.00"),
}


def _product_ids(engine: Engine) -> dict[str, int]:
    with Session(engine) as session:
        rows = session.exec(select(Product.code, Product.id)).all()
    return {code: product_id for code, product_id in rows if product_id is not None}


def _assert_rejected(engine: Engine, row: SQLModel, constraint: str) -> None:
    with Session(engine) as session, pytest.raises(IntegrityError, match=constraint):
        session.add(row)
        session.commit()


def _recommendation(inquiry: Inquiry, **overrides: object) -> InquiryRecommendation:
    assert inquiry.id is not None
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "inquiry_id": inquiry.id,
        "analysis_version": now,
        "checks_checked_at": now,
        "orchestrated_at": now,
        "status": "failed",
        "result": {"options": []},
        "recommended_at": now,
    }
    values.update(overrides)
    return InquiryRecommendation.model_validate(values)


# --- Seed -----------------------------------------------------------------------------


def test_seed_product_costs(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        products = session.exec(select(Product).where(col(Product.code).in_(PRODUCT_COSTS))).all()

    assert {p.code: p.unit_cost for p in products} == PRODUCT_COSTS


def test_seed_offer_costs(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        rows = session.exec(
            select(SupplierOffer, Product.code).join(
                Product, col(Product.id) == col(SupplierOffer.product_id)
            )
        ).all()

    costs = {(offer.supplier_name, code): offer.unit_cost for offer, code in rows}
    assert {key: costs[key] for key in OFFER_COSTS} == OFFER_COSTS


# --- Constraints ----------------------------------------------------------------------


@pytest.mark.parametrize("unit_cost", [Decimal("0.00"), Decimal("-1.00")])
def test_product_unit_cost_must_be_positive(migrated_engine: Engine, unit_cost: Decimal) -> None:
    row = Product(
        code="TEST-COST",
        name="Test",
        list_price=Decimal("10.00"),
        stock_quantity=1,
        unit_cost=unit_cost,
    )

    _assert_rejected(migrated_engine, row, "ck_products_unit_cost")


@pytest.mark.parametrize("unit_cost", [Decimal("0.00"), Decimal("-1.00")])
def test_supplier_offer_unit_cost_must_be_positive(
    migrated_engine: Engine, unit_cost: Decimal
) -> None:
    row = SupplierOffer(
        product_id=_product_ids(migrated_engine)["ABC-200"],
        supplier_name="Test",
        quantity=10,
        lead_time_days=3,
        unit_cost=unit_cost,
    )

    _assert_rejected(migrated_engine, row, "ck_supplier_offers_unit_cost")


def test_one_offer_per_supplier_and_product(migrated_engine: Engine) -> None:
    row = SupplierOffer(
        product_id=_product_ids(migrated_engine)["ABC-100"],
        supplier_name="Sensortech Polska",  # already offers ABC-100 in the seed
        quantity=10,
        lead_time_days=3,
        unit_cost=Decimal("95.00"),
    )

    _assert_rejected(migrated_engine, row, "uq_supplier_offers_product_id_supplier_name")


def test_recommendation_status_rejects_unknown_value(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    row = _recommendation(make_inquiry(received_at=datetime.now(UTC)))
    row.status = "partial"  # type: ignore[assignment]

    _assert_rejected(migrated_engine, row, "ck_inquiry_recommendations_status")


def test_one_recommendation_per_inquiry(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    with Session(migrated_engine) as session:
        session.add(_recommendation(inquiry))
        session.commit()

    _assert_rejected(
        migrated_engine, _recommendation(inquiry), "uq_inquiry_recommendations_inquiry_id"
    )


def test_deleting_inquiry_deletes_recommendation(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    with Session(migrated_engine) as session:
        session.add(_recommendation(inquiry, status="completed"))
        session.commit()
        stored = session.exec(
            select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry.id)
        ).one()
        assert (stored.status, stored.result) == ("completed", {"options": []})

    with Session(migrated_engine) as session:
        session.delete(session.get_one(Inquiry, inquiry.id))
        session.commit()
        remaining = session.exec(
            select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry.id)
        ).all()

    assert remaining == []
