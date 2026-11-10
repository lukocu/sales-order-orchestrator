"""Run, store and read the checks of an analysed inquiry (independent of FastAPI).

The checks always get their own tracing run with deterministic steps only, so a standard
inquiry costs 0 tokens also when the analysis used a model. Inputs are read in one short
session, the steps run without a database connection held, and the result is written in
another short session that locks the analysis row: a result computed from an analysis
version that is no longer current is dropped (the newer run wins).
"""

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine, Select, case, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.checks.models import Customer, InquiryChecks, Product
from app.checks.rules import (
    CustomerRecord,
    ProductRecord,
    check_credit,
    check_discount,
    check_price,
    check_stock,
    classify,
    find_product,
    match_customer,
)
from app.checks.schema import CheckResults, ExceptionType, NeedsInputReason, Outcome
from app.inquiries.models import Inquiry
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import ParsedFields
from app.tracing import run
from app.tracing.summary import RunSummary, get_run_summary

logger = logging.getLogger(__name__)

SUBJECT_TYPE = "inquiry"

# Analysis fields the checks depend on; their uncertainty is shown next to the result.
CheckInput = Literal["customer", "product_code", "quantity"]
CHECK_INPUTS: tuple[CheckInput, ...] = ("customer", "product_code", "quantity")


class NoAnalysis(Exception):
    """The inquiry has no analysis to check (or does not exist)."""


class ChecksView(BaseModel):
    outcome: Outcome
    exception_type: ExceptionType | None
    reasons: list[NeedsInputReason]
    results: CheckResults
    checked_at: datetime
    stale: bool  # computed from an analysis version that is no longer current
    uncertain_inputs: list[CheckInput]  # uncertain analysis fields the checks used
    run: RunSummary | None  # None when the run could not be traced or was deleted


def analysis_version(analysis: InquiryAnalysis) -> datetime:
    """The version the checks are computed from: the last correction, else the analysis."""
    return analysis.corrected_at if analysis.corrected_at is not None else analysis.analyzed_at


def run_checks(engine: Engine, inquiry_id: int) -> None:
    """Check the current analysis in a new run and store the result if it is still current.

    Raises `NoAnalysis` when there is nothing to check; a failing check propagates after its
    step and the run are recorded as failed, and the stored result stays as it was.
    """
    with Session(engine) as session:
        row = session.exec(
            select(InquiryAnalysis, Inquiry.sender_email)
            .join(Inquiry, col(Inquiry.id) == col(InquiryAnalysis.inquiry_id))
            .where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
        ).first()
        if row is None:
            raise NoAnalysis
        analysis, sender_email = row
        version = analysis_version(analysis)
        fields = ParsedFields.model_validate(analysis.fields)
        customers = [_customer_record(c) for c in session.exec(select(Customer)).all()]
        products = [_product_record(p) for p in session.exec(select(Product)).all()]

    with run(engine, subject_type=SUBJECT_TYPE, subject_id=str(inquiry_id)) as traced:
        with traced.step("match-customer", kind="deterministic"):
            customer_check, customer = match_customer(fields, sender_email, customers)
        with traced.step("check-stock", kind="deterministic"):
            product = find_product(fields, products)
            stock = check_stock(fields, product)
        with traced.step("check-price", kind="deterministic"):
            price = check_price(fields, customer, product)
        with traced.step("check-discount", kind="deterministic"):
            discount = check_discount(fields, customer, price)
        with traced.step("check-credit", kind="deterministic"):
            credit = check_credit(customer, price)
        with traced.step("classify", kind="deterministic"):
            classification = classify(
                fields, product, customer_check, stock, price, discount, credit
            )

    values: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "run_id": traced.id,
        "analysis_version": version,
        "outcome": classification.outcome,
        "exception_type": classification.exception_type,
        "results": classification.results.model_dump(mode="json"),
        "checked_at": datetime.now(UTC),
    }
    statement = insert(InquiryChecks).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["inquiry_id"],
        set_={name: statement.excluded[name] for name in values if name != "inquiry_id"},
    )
    with Session(engine) as session:
        # Locked, so the analysis cannot change between the version check and the write.
        current = session.exec(
            select(InquiryAnalysis)
            .where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
            .with_for_update()
        ).first()
        if current is None or analysis_version(current) != version:
            return  # replaced or corrected meanwhile: that newer version gets its own run
        session.exec(statement)
        session.commit()


def get_checks_view(session: Session, analysis: InquiryAnalysis) -> ChecksView | None:
    """The stored result for the analysis' inquiry; None when it was never checked.

    Also None when the stored result no longer matches `CheckResults` (schema changed without
    a data migration): the analysis stays readable and the checks can simply be re-run.
    """
    checks = session.exec(
        select(InquiryChecks).where(col(InquiryChecks.inquiry_id) == analysis.inquiry_id)
    ).first()
    if checks is None:
        return None
    try:
        results = CheckResults.model_validate(checks.results)
    except ValidationError as error:
        # Class and inquiry id only: the validation message would quote the stored values.
        logger.error(
            "Stored check result of inquiry %s does not match the schema: %s",
            analysis.inquiry_id,
            type(error).__name__,
        )
        return None
    return ChecksView(
        outcome=checks.outcome,
        exception_type=checks.exception_type,
        reasons=results.reasons,
        results=results,
        checked_at=checks.checked_at,
        stale=checks.analysis_version != analysis_version(analysis),
        uncertain_inputs=[field for field in CHECK_INPUTS if field in analysis.uncertain],
        run=None if checks.run_id is None else get_run_summary(session, checks.run_id),
    )


def current_outcome() -> ColumnElement[Any]:
    """The inquiry's outcome when its result matches the current analysis version, else NULL.

    Valid only on a statement passed through `with_current_outcome`.
    """
    current_version = func.coalesce(
        col(InquiryAnalysis.corrected_at), col(InquiryAnalysis.analyzed_at)
    )
    return case(
        (col(InquiryChecks.analysis_version) == current_version, col(InquiryChecks.outcome)),
        else_=None,
    )


def with_current_outcome[S: Select[*tuple[Any, ...]]](statement: S) -> S:
    """Outer-join the check result and the analysis of `Inquiry` rows (one row each)."""
    return statement.outerjoin(
        InquiryChecks, col(InquiryChecks.inquiry_id) == col(Inquiry.id)
    ).outerjoin(InquiryAnalysis, col(InquiryAnalysis.inquiry_id) == col(Inquiry.id))


def _customer_record(customer: Customer) -> CustomerRecord:
    assert customer.id is not None
    return CustomerRecord(
        id=customer.id,
        name=customer.name,
        email_domain=customer.email_domain,
        standard_discount_percent=customer.standard_discount_percent,
        credit_limit=customer.credit_limit,
        credit_balance=customer.credit_balance,
        credit_blocked=customer.credit_blocked,
    )


def _product_record(product: Product) -> ProductRecord:
    assert product.id is not None
    return ProductRecord(
        id=product.id,
        code=product.code,
        name=product.name,
        list_price=product.list_price,
        stock_quantity=product.stock_quantity,
    )
