"""Evaluate, store and read the policy verdict of an inquiry's recommended option.

Mirrors `app.recommendation.service`: inputs are read from the current data in one short
session (the stored recommendation, its chosen option, the current check result and the
thresholds of `policy_rules`), the rules run in their own tracing run (one deterministic
`rules` step) and the verdict is written once, in another short session that locks the
analysis row. A verdict computed from a recommendation that was replaced (another
`recommended_at`), turned `failed` or deleted meanwhile is dropped (the newer run decides).

The verdict is pinned to the recommendation by its `recommended_at`. Only the recommendation
models are imported here, never `app.recommendation.service`, which calls this module.
Logs carry the error class and the inquiry id only, never inquiry content.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Engine, delete
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.checks.schema import CheckResults
from app.checks.service import analysis_version, current_checks, lock_analysis
from app.parsing.models import InquiryAnalysis
from app.policy.models import InquiryPolicyVerdict, PolicyRule
from app.policy.rules import PolicyInputs, PolicyThresholds, evaluate
from app.policy.schema import PolicyResult, ThresholdCode
from app.recommendation.models import InquiryRecommendation
from app.recommendation.pin import is_current
from app.recommendation.schema import RecommendationResult
from app.tracing import run
from app.tracing.summary import RunSummary, get_run_summary

logger = logging.getLogger(__name__)

SUBJECT_TYPE = "inquiry"


class NothingToEvaluate(Exception):
    """No current recommendation with a chosen option: none stored, not `completed`, no
    choice or chosen option, or not computed from the current analysis version, check result
    and orchestration."""


class PolicyView(PolicyResult):
    evaluated_at: datetime
    # evaluated for another recommendation than the stored one, or the recommendation itself
    # is stale (set by the analysis view)
    stale: bool
    run: RunSummary | None  # None when the run could not be traced or was deleted


@dataclass(frozen=True)
class _Inputs:
    recommendation_id: int
    recommended_at: datetime  # identifies the recommendation the verdict evaluates
    inputs: PolicyInputs
    thresholds: PolicyThresholds


def run_policy(engine: Engine, inquiry_id: int) -> None:
    """Evaluate the current recommendation's chosen option in a new run and store the verdict
    if the recommendation is still the same.

    Raises `NothingToEvaluate` when there is no current recommendation with a chosen option,
    after dropping a stored verdict that no longer belongs to one. Unexpected errors
    propagate after the run is recorded as failed; the stored verdict stays as it was.
    """
    try:
        with Session(engine) as session:
            inputs = _read_inputs(session, inquiry_id)
    except NothingToEvaluate:
        _drop_outdated(engine, inquiry_id)
        raise

    with (
        run(engine, subject_type=SUBJECT_TYPE, subject_id=str(inquiry_id)) as traced,
        traced.step("rules", kind="deterministic"),
    ):
        result = evaluate(inputs.inputs, inputs.thresholds)
    _store(engine, inquiry_id, inputs, traced.id, result)


def policy_after_recommendation(engine: Engine, inquiry_id: int) -> None:
    """After a recommendation attempt: evaluate the policy, else drop a verdict of old data.

    Never raises: unexpected errors are logged (class and inquiry id only) and leave the
    stored verdict as it was.
    """
    try:
        run_policy(engine, inquiry_id)
    except NothingToEvaluate:
        pass  # run_policy already dropped a verdict of old data
    except Exception as error:
        logger.warning(
            "Policy evaluation failed for inquiry %s: %s", inquiry_id, type(error).__name__
        )


def get_policy_view(session: Session, analysis: InquiryAnalysis) -> PolicyView | None:
    """The stored verdict for the analysis' inquiry; None when there is none.

    Also None when the stored result no longer matches `PolicyResult` (schema changed without
    a data migration): the analysis stays readable and the policy can be re-run. `stale`
    compares only the recommendation pin; the analysis view adds the recommendation's own
    staleness.
    """
    row = session.exec(
        select(InquiryPolicyVerdict).where(
            col(InquiryPolicyVerdict.inquiry_id) == analysis.inquiry_id
        )
    ).first()
    if row is None:
        return None
    try:
        result = PolicyResult.model_validate(row.result)
    except ValidationError as error:
        # Class and inquiry id only: the validation message would quote the stored values.
        logger.error(
            "Stored policy verdict of inquiry %s does not match the schema: %s",
            analysis.inquiry_id,
            type(error).__name__,
        )
        return None
    recommended_at = session.exec(
        select(InquiryRecommendation.recommended_at).where(
            col(InquiryRecommendation.inquiry_id) == analysis.inquiry_id
        )
    ).first()
    return PolicyView(
        option_id=result.option_id,
        rules=result.rules,
        outcome=result.outcome,
        thresholds_are_examples=result.thresholds_are_examples,
        evaluated_at=row.evaluated_at,
        stale=row.recommended_at != recommended_at,
        run=None if row.run_id is None else get_run_summary(session, row.run_id),
    )


def _read_inputs(session: Session, inquiry_id: int) -> _Inputs:
    analysis = session.exec(
        select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
    ).first()
    if analysis is None:
        raise NothingToEvaluate
    recommendation = session.exec(
        select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry_id)
    ).first()
    if recommendation is None or recommendation.status != "completed":
        raise NothingToEvaluate
    assert recommendation.id is not None
    try:
        result = RecommendationResult.model_validate(recommendation.result)
    except ValidationError as error:
        # Hidden in the view as well; the recommendation has to be re-run first.
        logger.error(
            "Stored recommendation result of inquiry %s does not match the schema: %s",
            inquiry_id,
            type(error).__name__,
        )
        raise NothingToEvaluate from None
    if result.choice is None:
        raise NothingToEvaluate
    option_id = result.choice.option_id
    option = next((o for o in result.options if o.id == option_id), None)
    if option is None:
        raise NothingToEvaluate
    # The same pin as the recommendation view: analysis version, check result, orchestration.
    if not is_current(session, recommendation, analysis):
        raise NothingToEvaluate
    checks = current_checks(session, inquiry_id, analysis_version(analysis))
    if checks is None:
        raise NothingToEvaluate
    results = CheckResults.model_validate(checks.results)
    return _Inputs(
        recommendation_id=recommendation.id,
        recommended_at=recommendation.recommended_at,
        inputs=PolicyInputs(
            option_id=option.id,
            value=option.value,
            margin_percent=option.margin_percent,
            discount=results.discount,
            list_price=results.price.list_price,
            credit=results.credit,
        ),
        thresholds=_thresholds(session),
    )


def _thresholds(session: Session) -> PolicyThresholds:
    """The configured thresholds; a missing row leaves its rule not evaluated."""
    rules = {rule.code: rule for rule in session.exec(select(PolicyRule)).all()}

    def threshold(code: ThresholdCode) -> Decimal | None:
        rule = rules.get(code)
        return None if rule is None else rule.threshold

    return PolicyThresholds(
        margin_min_percent=threshold("margin_min_percent"),
        discount_max_percent=threshold("discount_max_percent"),
        order_value_max=threshold("order_value_max"),
        # One example threshold makes the whole verdict an example.
        are_examples=any(rule.is_example for rule in rules.values()),
    )


def _store(
    engine: Engine,
    inquiry_id: int,
    inputs: _Inputs,
    run_id: int | None,
    result: PolicyResult,
) -> None:
    values: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "recommendation_id": inputs.recommendation_id,
        "run_id": run_id,
        "recommended_at": inputs.recommended_at,
        "outcome": result.outcome,
        "result": result.model_dump(mode="json"),
        "evaluated_at": datetime.now(UTC),
    }
    statement = insert(InquiryPolicyVerdict).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["inquiry_id"],
        set_={name: statement.excluded[name] for name in values if name != "inquiry_id"},
    )
    with Session(engine) as session:
        analysis = lock_analysis(session, inquiry_id)
        if analysis is None:
            return  # the inquiry was deleted meanwhile
        recommendation = session.exec(
            select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry_id)
        ).first()
        if (
            recommendation is None
            or recommendation.id != inputs.recommendation_id
            or recommendation.status != "completed"
            or recommendation.recommended_at != inputs.recommended_at
        ):
            return  # recommended again, failed or deleted meanwhile: that run decides
        if not is_current(session, recommendation, analysis):
            return  # re-checked or orchestrated again meanwhile: that chain decides
        session.exec(statement)
        session.commit()


def _drop_outdated(engine: Engine, inquiry_id: int) -> None:
    """Delete the stored verdict when it no longer belongs to a current recommendation.

    That is when the stored recommendation is gone, not `completed`, recommended again
    (another `recommended_at`) or not computed from the current analysis version, check
    result and orchestration. A verdict of
    the current recommendation is kept, so an older call never deletes the result of a
    newer run.
    """
    with Session(engine) as session:
        analysis = lock_analysis(session, inquiry_id)
        if analysis is None:
            return  # the inquiry was deleted; its verdict cascades
        verdict = session.exec(
            select(InquiryPolicyVerdict).where(col(InquiryPolicyVerdict.inquiry_id) == inquiry_id)
        ).first()
        if verdict is None:
            return
        recommendation = session.exec(
            select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry_id)
        ).first()
        outdated = (
            recommendation is None
            or recommendation.status != "completed"
            or recommendation.recommended_at != verdict.recommended_at
            or not is_current(session, recommendation, analysis)
        )
        if outdated:
            session.exec(
                delete(InquiryPolicyVerdict).where(
                    col(InquiryPolicyVerdict.inquiry_id) == inquiry_id
                )
            )
            session.commit()
