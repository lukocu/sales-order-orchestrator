"""Run, store and read the recommendation of an inquiry with an orchestrated exception.

Mirrors `app.orchestration.service`: inputs are read in one short session (the current
analysis, its check result, its orchestration and the priced company data), the
recommendation runs in its own tracing run (`options`, then one `choose` step per recommender
attempt) and the result is written once, in another short session that locks the analysis
row. A result computed from an analysis version, a check result or an orchestration that is
no longer current is dropped (the newer run wins). An orchestration is identified by its
`orchestrated_at`.

Expected failures (recommender error, rejected choice) end in a stored `failed` result that
keeps the options, not in an exception. Logs carry the error class and the inquiry id only,
never inquiry content.
"""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Engine, delete
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.checks.models import Product
from app.checks.schema import CheckResults
from app.checks.service import CHECK_INPUTS, analysis_version, current_checks, lock_analysis
from app.orchestration.models import InquiryOrchestration, SupplierOffer
from app.orchestration.schema import (
    OrchestrationResult,
    SubstituteAvailabilityResult,
    SubstituteCompatibilityResult,
)
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import ParsedFields
from app.recommendation.models import InquiryRecommendation, RecommendationStatus
from app.recommendation.options import (
    PricedProduct,
    RecommendationInputs,
    build_options,
    recommendation_facts,
)
from app.recommendation.recommender import (
    ChoiceRejected,
    Recommender,
    RecommenderError,
    RecommenderFailed,
    RecommenderNotConfigured,
    RecommenderRateLimited,
    validate_choice,
)
from app.recommendation.schema import (
    RecommendationError,
    RecommendationFacts,
    RecommendationOption,
    RecommendationResult,
    RecommenderChoice,
)
from app.tracing import RunHandle, run
from app.tracing.summary import RunSummary, get_run_summary

logger = logging.getLogger(__name__)

SUBJECT_TYPE = "inquiry"
RECOMMENDER_ATTEMPTS = 2
RECOMMENDER_RETRY_DELAY_S = 1.0
# Orchestration statuses whose completed tasks can be turned into options.
RECOMMENDABLE = ("completed", "partial")


class NothingToRecommend(Exception):
    """The current analysis has no check result with an exception, or no current
    orchestration that is `completed` or `partial`."""


class RecommendationView(RecommendationResult):
    status: RecommendationStatus
    recommended_at: datetime
    # computed from an analysis version, a check result or an orchestration that is no
    # longer current
    stale: bool
    run: RunSummary | None  # None when the run could not be traced or was deleted


@dataclass(frozen=True)
class _Inputs:
    version: datetime
    checks_checked_at: datetime  # identifies the check result the recommendation used
    orchestrated_at: datetime  # identifies the orchestration the recommendation used
    inputs: RecommendationInputs


def run_recommendation(
    engine: Engine,
    inquiry_id: int,
    recommender: Recommender,
    *,
    attempts: int = RECOMMENDER_ATTEMPTS,
    retry_delay_s: float = RECOMMENDER_RETRY_DELAY_S,
) -> None:
    """Recommend for the current orchestration in a new run and store the result if current.

    Raises `NothingToRecommend` when there is no current exception with a `completed` or
    `partial` orchestration, after dropping a stored recommendation of old data. Unexpected
    errors propagate after the run is recorded as failed; the stored result stays as it was.
    `attempts` bounds the recommender calls (a transient error is retried while attempts
    remain).
    """
    try:
        with Session(engine) as session:
            inputs = _read_inputs(session, inquiry_id)
    except NothingToRecommend:
        _drop_outdated(engine, inquiry_id)
        raise

    with run(engine, subject_type=SUBJECT_TYPE, subject_id=str(inquiry_id)) as traced:
        result = _recommend(traced, recommender, inquiry_id, inputs, attempts, retry_delay_s)
    status: RecommendationStatus = "failed" if result.error is not None else "completed"
    _store(engine, inquiry_id, inputs, traced.id, status, result)


def recommend_after_orchestration(
    engine: Engine, inquiry_id: int, recommender: Recommender
) -> None:
    """After an orchestration attempt: recommend, else drop a recommendation of old data.

    Runs inside the analysis, correction and orchestration requests, so the recommender gets
    a single attempt: a transient error ends in `failed` and "Re-run recommendation" retries
    it. Never raises: unexpected errors are logged (class and inquiry id only) and leave the
    stored recommendation as it was.
    """
    try:
        run_recommendation(engine, inquiry_id, recommender, attempts=1)
    except NothingToRecommend:
        pass  # run_recommendation already dropped a recommendation of old data
    except Exception as error:
        logger.warning("Recommendation failed for inquiry %s: %s", inquiry_id, type(error).__name__)


def get_recommendation_view(
    session: Session, analysis: InquiryAnalysis
) -> RecommendationView | None:
    """The stored recommendation for the analysis' inquiry; None when there is none.

    Also None when the stored result no longer matches `RecommendationResult` (schema changed
    without a data migration): the analysis stays readable and the recommendation can be
    re-run.
    """
    row = session.exec(
        select(InquiryRecommendation).where(
            col(InquiryRecommendation.inquiry_id) == analysis.inquiry_id
        )
    ).first()
    if row is None:
        return None
    try:
        result = RecommendationResult.model_validate(row.result)
    except ValidationError as error:
        # Class and inquiry id only: the validation message would quote the stored values.
        logger.error(
            "Stored recommendation result of inquiry %s does not match the schema: %s",
            analysis.inquiry_id,
            type(error).__name__,
        )
        return None
    version = analysis_version(analysis)
    checks = current_checks(session, analysis.inquiry_id, version)
    orchestrated_at = session.exec(
        select(InquiryOrchestration.orchestrated_at).where(
            col(InquiryOrchestration.inquiry_id) == analysis.inquiry_id
        )
    ).first()
    return RecommendationView(
        recommender=result.recommender,
        options=result.options,
        choice=result.choice,
        choice_steps=result.choice_steps,
        error=result.error,
        status=row.status,
        recommended_at=row.recommended_at,
        stale=not _pinned_to(
            row, version, None if checks is None else checks.checked_at, orchestrated_at
        ),
        run=None if row.run_id is None else get_run_summary(session, row.run_id),
    )


def _pinned_to(
    row: InquiryRecommendation,
    version: datetime,
    checks_checked_at: datetime | None,
    orchestrated_at: datetime | None,
) -> bool:
    """True when the row was computed from exactly these current values."""
    return (
        row.analysis_version == version
        and row.checks_checked_at == checks_checked_at
        and row.orchestrated_at == orchestrated_at
    )


def _read_inputs(session: Session, inquiry_id: int) -> _Inputs:
    analysis = session.exec(
        select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
    ).first()
    if analysis is None:
        raise NothingToRecommend
    version = analysis_version(analysis)
    checks = current_checks(session, inquiry_id, version)
    if checks is None or checks.outcome != "exception":
        raise NothingToRecommend
    orchestration = _current_orchestration(session, inquiry_id, version, checks.checked_at)
    if orchestration is None or orchestration.status not in RECOMMENDABLE:
        raise NothingToRecommend
    try:
        result = OrchestrationResult.model_validate(orchestration.result)
    except ValidationError as error:
        # Hidden in the view as well; the orchestration has to be re-run first.
        logger.error(
            "Stored orchestration result of inquiry %s does not match the schema: %s",
            inquiry_id,
            type(error).__name__,
        )
        raise NothingToRecommend from None
    fields = ParsedFields.model_validate(analysis.fields)
    results = CheckResults.model_validate(checks.results)
    stock, discount = results.stock, results.price.discount_percent
    if (
        stock.product_code is None
        or stock.requested is None
        or stock.available is None
        or stock.shortage is None
        or discount is None
    ):
        # An exception always has a found product and a matched customer (needs_input
        # otherwise); treat a row without them as nothing to recommend.
        raise NothingToRecommend

    codes = {stock.product_code} | _substitute_codes(result)
    products = {
        p.code: PricedProduct(
            code=p.code, name=p.name, list_price=p.list_price, unit_cost=p.unit_cost
        )
        for p in session.exec(select(Product).where(col(Product.code).in_(codes))).all()
    }
    product = products.get(stock.product_code)
    if product is None:
        raise NothingToRecommend
    supplier_costs: dict[tuple[str, str], Decimal] = {
        (offer.supplier_name, stock.product_code): offer.unit_cost
        for offer in session.exec(
            select(SupplierOffer)
            .join(Product, col(Product.id) == col(SupplierOffer.product_id))
            .where(col(Product.code) == stock.product_code)
            .order_by(col(SupplierOffer.id))
        ).all()
    }
    inputs = RecommendationInputs(
        product=product,
        requested=stock.requested,
        available=stock.available,
        shortage=stock.shortage,
        deadline=fields.deadline,
        reference_date=analysis.reference_date,
        consent=result.consent,
        discount_percent=discount,
        products_by_code={code: p for code, p in products.items() if code != product.code},
        supplier_costs=supplier_costs,
        tasks=result.tasks,
        # As in the checks view: the uncertain analysis fields the checks used.
        uncertain_inputs=[field for field in CHECK_INPUTS if field in analysis.uncertain],
    )
    return _Inputs(
        version=version,
        checks_checked_at=checks.checked_at,
        orchestrated_at=orchestration.orchestrated_at,
        inputs=inputs,
    )


def _substitute_codes(result: OrchestrationResult) -> set[str]:
    codes: set[str] = set()
    for task in result.tasks:
        if isinstance(task.result, SubstituteCompatibilityResult | SubstituteAvailabilityResult):
            codes.update(c.code for c in task.result.candidates)
    return codes


def _current_orchestration(
    session: Session, inquiry_id: int, version: datetime, checks_checked_at: datetime
) -> InquiryOrchestration | None:
    """The orchestration computed from this analysis version and check result, if any."""
    return session.exec(
        select(InquiryOrchestration).where(
            col(InquiryOrchestration.inquiry_id) == inquiry_id,
            col(InquiryOrchestration.analysis_version) == version,
            col(InquiryOrchestration.checks_checked_at) == checks_checked_at,
        )
    ).first()


def _recommend(
    traced: RunHandle,
    recommender: Recommender,
    inquiry_id: int,
    inputs: _Inputs,
    attempts: int,
    retry_delay_s: float,
) -> RecommendationResult:
    """Build the options, let the recommender choose and validate the choice."""
    result = RecommendationResult(recommender=recommender.name)
    with traced.step("options", kind="deterministic"):
        result.options = build_options(inputs.inputs)
        facts = recommendation_facts(inputs.inputs)

    choice, result.choice_steps, result.error = _choose(
        traced, recommender, inquiry_id, facts, result.options, attempts, retry_delay_s
    )
    if choice is None:
        return result
    try:
        validate_choice(choice, result.options)
        result.choice = choice
    except ChoiceRejected as rejected:
        # A result, not a failure: the choice step ended ok; the reason is stored and no
        # option is shown as chosen.
        logger.warning(
            "Recommendation of inquiry %s: choice rejected (%s)", inquiry_id, rejected.code
        )
        result.error = RecommendationError(
            kind="choice_rejected", code=rejected.code, message=str(rejected)
        )
    return result


def _choose(
    traced: RunHandle,
    recommender: Recommender,
    inquiry_id: int,
    facts: RecommendationFacts,
    options: list[RecommendationOption],
    attempts: int,
    retry_delay_s: float,
) -> tuple[RecommenderChoice | None, list[str], RecommendationError | None]:
    """The recommender's choice; a transient error is retried as `choose#2` while attempts
    remain."""
    steps: list[str] = []
    for attempt in range(1, attempts + 1):
        name = "choose" if attempt == 1 else f"choose#{attempt}"
        steps.append(name)
        try:
            with traced.step(name, kind=recommender.step_kind) as step:
                try:
                    output = recommender.choose(facts, options)
                except RecommenderError as error:
                    # The provider may have billed the call before it failed.
                    if error.usage is not None:
                        step.record_usage(error.usage)
                    raise
                if output.usage is not None:
                    step.record_usage(output.usage)
        except RecommenderError as error:
            if error.transient and attempt < attempts:
                time.sleep(retry_delay_s)
                continue
            logger.warning(
                "Recommendation of inquiry %s: %s failed with %s",
                inquiry_id,
                name,
                type(error).__name__,
            )
            return (
                None,
                steps,
                RecommendationError(
                    kind="recommender_failed",
                    code=_recommender_error_code(error),
                    message=str(error),
                ),
            )
        return output.choice, steps, None
    raise AssertionError("unreachable")  # pragma: no cover


def _recommender_error_code(error: RecommenderError) -> str:
    if isinstance(error, RecommenderNotConfigured):
        return "not_configured"
    if isinstance(error, RecommenderRateLimited):
        return "rate_limited"
    if isinstance(error, RecommenderFailed) and error.transient:
        return "unavailable"
    return "failed"


def _store(
    engine: Engine,
    inquiry_id: int,
    inputs: _Inputs,
    run_id: int | None,
    status: RecommendationStatus,
    result: RecommendationResult,
) -> None:
    values: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "run_id": run_id,
        "analysis_version": inputs.version,
        "checks_checked_at": inputs.checks_checked_at,
        "orchestrated_at": inputs.orchestrated_at,
        "status": status,
        "result": result.model_dump(mode="json"),
        "recommended_at": datetime.now(UTC),
    }
    statement = insert(InquiryRecommendation).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["inquiry_id"],
        set_={name: statement.excluded[name] for name in values if name != "inquiry_id"},
    )
    with Session(engine) as session:
        current = lock_analysis(session, inquiry_id)
        if current is None or analysis_version(current) != inputs.version:
            return  # replaced or corrected meanwhile: that newer version gets its own run
        checks = current_checks(session, inquiry_id, inputs.version)
        if checks is None or checks.outcome != "exception":
            return  # re-checked meanwhile without an exception
        if checks.checked_at != inputs.checks_checked_at:
            return  # re-checked meanwhile: the run after that check result decides
        orchestration = _current_orchestration(
            session, inquiry_id, inputs.version, inputs.checks_checked_at
        )
        if orchestration is None or orchestration.orchestrated_at != inputs.orchestrated_at:
            return  # orchestrated again meanwhile: the run after that orchestration decides
        session.exec(statement)
        session.commit()


def _drop_outdated(engine: Engine, inquiry_id: int) -> None:
    """Delete the stored recommendation when it no longer belongs to the current data.

    That is when its pinned analysis version, check result or orchestration is not the
    current one, or the current orchestration is `failed` or missing. A row pinned to the
    current data is kept, so an older call never deletes the result of a newer run.
    """
    with Session(engine) as session:
        analysis = lock_analysis(session, inquiry_id)
        if analysis is None:
            return  # the inquiry was deleted; its recommendation cascades
        row = session.exec(
            select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry_id)
        ).first()
        if row is None:
            return
        version = analysis_version(analysis)
        checks = current_checks(session, inquiry_id, version)
        orchestration = session.exec(
            select(InquiryOrchestration).where(col(InquiryOrchestration.inquiry_id) == inquiry_id)
        ).first()
        outdated = (
            orchestration is None
            or orchestration.status == "failed"
            or not _pinned_to(
                row,
                version,
                None if checks is None else checks.checked_at,
                orchestration.orchestrated_at,
            )
        )
        if outdated:
            session.exec(
                delete(InquiryRecommendation).where(
                    col(InquiryRecommendation.inquiry_id) == inquiry_id
                )
            )
            session.commit()
