from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.checks.models import Customer, InquiryChecks, Product
from app.checks.schema import CheckResults
from app.inquiries.models import Inquiry
from tests.conftest import InquiryFactory
from tests.test_checks_rules import SEED_CUSTOMERS, SEED_PRODUCTS


def _results() -> CheckResults:
    return CheckResults.model_validate(
        {
            "customer": {"status": "missing"},
            "stock": {"status": "skipped"},
            "price": {"status": "skipped"},
            "discount": {"status": "skipped"},
            "credit": {"status": "skipped"},
            "reasons": ["customer_missing", "product_missing", "quantity_missing"],
        }
    )


def _checks(inquiry: Inquiry, **overrides: object) -> InquiryChecks:
    assert inquiry.id is not None
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "inquiry_id": inquiry.id,
        "analysis_version": now,
        "outcome": "needs_input",
        "exception_type": None,
        "results": _results().model_dump(mode="json"),
        "checked_at": now,
    }
    values.update(overrides)
    return InquiryChecks.model_validate(values)


def test_seed_matches_company_data(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        customers = session.exec(select(Customer)).all()
        products = session.exec(select(Product)).all()

    by_name = {c.name: c for c in customers}
    for expected in SEED_CUSTOMERS:
        stored = by_name[expected.name]
        assert stored.email_domain == expected.email_domain
        assert stored.standard_discount_percent == expected.standard_discount_percent
        assert stored.credit_limit == expected.credit_limit
        assert stored.credit_balance == expected.credit_balance
        assert stored.credit_blocked == expected.credit_blocked
    by_code = {p.code: p for p in products}
    for product in SEED_PRODUCTS:
        stored_product = by_code[product.code]
        assert stored_product.name == product.name
        assert stored_product.list_price == product.list_price
        assert stored_product.stock_quantity == product.stock_quantity


def test_deleting_inquiry_deletes_checks(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    with Session(migrated_engine) as session:
        session.add(_checks(inquiry))
        session.commit()

    with Session(migrated_engine) as session:
        session.delete(session.get_one(Inquiry, inquiry.id))
        session.commit()
        remaining = session.exec(
            select(InquiryChecks).where(col(InquiryChecks.inquiry_id) == inquiry.id)
        ).all()

    assert remaining == []


def test_stored_results_read_back(migrated_engine: Engine, make_inquiry: InquiryFactory) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    with Session(migrated_engine) as session:
        session.add(_checks(inquiry))
        session.commit()
        stored = session.exec(
            select(InquiryChecks).where(col(InquiryChecks.inquiry_id) == inquiry.id)
        ).one()

    assert CheckResults.model_validate(stored.results) == _results()


def test_outcome_check_rejects_unknown_value(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    checks = _checks(make_inquiry(received_at=datetime.now(UTC)))
    checks.outcome = "maybe"  # type: ignore[assignment]

    with (
        Session(migrated_engine) as session,
        pytest.raises(IntegrityError, match="ck_inquiry_checks_outcome"),
    ):
        session.add(checks)
        session.commit()


def test_exception_type_requires_exception_outcome(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    checks = _checks(
        make_inquiry(received_at=datetime.now(UTC)), exception_type="insufficient_stock"
    )

    with (
        Session(migrated_engine) as session,
        pytest.raises(IntegrityError, match="ck_inquiry_checks_exception_type_with_outcome"),
    ):
        session.add(checks)
        session.commit()
