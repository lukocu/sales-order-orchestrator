"""Run, store and read the orchestration of an inquiry with a stock exception.

Mirrors `app.checks.service`: inputs are read in one short session (the current analysis and
its check result), the orchestration runs in its own tracing run (plan, validate-plan,
match-capabilities, then one step per agent attempt) and the result is written once, in
another short session that locks the analysis row. A result computed from an analysis version
that is no longer current, or from a check result that was replaced or is no longer an
exception, is dropped (the newer run wins). A check result is identified by its `checked_at`:
a re-check at the same analysis version replaces it.

Expected failures (planner error, rejected plan, capability without an agent, failing agent)
end in a stored `failed` or `partial` result, not in an exception. Logs carry the error class
and the inquiry id only, never inquiry content.
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Engine, delete
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.checks.models import InquiryChecks, Product
from app.checks.schema import CheckResults
from app.checks.service import analysis_version, current_checks, lock_analysis
from app.draft.drafter import Drafter
from app.orchestration.agents import AgentInput
from app.orchestration.executor import PlanItem, execute
from app.orchestration.models import InquiryOrchestration
from app.orchestration.planning import (
    Planner,
    PlannerError,
    PlannerFailed,
    PlannerNotConfigured,
    PlannerRateLimited,
    PlanRejected,
    substitute_consent,
    validate_plan,
)
from app.orchestration.registry import AGENTS, AgentSpec, CapabilityMismatch, match_agents
from app.orchestration.schema import (
    OrchestrationError,
    OrchestrationResult,
    OrchestrationStatus,
    PlanFacts,
    PlannerChoice,
)
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import ParsedFields
from app.recommendation.models import InquiryRecommendation
from app.recommendation.recommender import Recommender
from app.recommendation.service import recommend_after_orchestration
from app.tracing import RunHandle, run
from app.tracing.summary import RunSummary, get_run_summary

logger = logging.getLogger(__name__)

SUBJECT_TYPE = "inquiry"
PLANNER_ATTEMPTS = 2
PLANNER_RETRY_DELAY_S = 1.0
AGENT_RETRY_DELAY_S = 0.5


class NothingToOrchestrate(Exception):
    """The current analysis has no check result, or its check result is not an exception."""


class OrchestrationView(OrchestrationResult):
    status: OrchestrationStatus
    orchestrated_at: datetime
    stale: bool  # computed from an analysis version or a check result that is no longer current
    run: RunSummary | None  # None when the run could not be traced or was deleted


@dataclass(frozen=True)
class _Inputs:
    version: datetime
    checks_checked_at: datetime  # identifies the check result the orchestration used
    facts: PlanFacts
    agent_input: AgentInput


def run_orchestration(
    engine: Engine,
    inquiry_id: int,
    planner: Planner,
    *,
    agents: Sequence[AgentSpec] = AGENTS,
    planner_attempts: int = PLANNER_ATTEMPTS,
    planner_retry_delay_s: float = PLANNER_RETRY_DELAY_S,
    agent_retry_delay_s: float = AGENT_RETRY_DELAY_S,
) -> None:
    """Orchestrate the current analysis in a new run and store the result if still current.

    Raises `NothingToOrchestrate` when the current analysis has no exception to orchestrate.
    Unexpected errors propagate after the run is recorded as failed; the stored result stays
    as it was. `planner_attempts` bounds the planner calls (a transient error is retried
    while attempts remain); `agents` and the retry delays exist for tests.
    """
    with Session(engine) as session:
        inputs = _read_inputs(session, inquiry_id)

    with run(engine, subject_type=SUBJECT_TYPE, subject_id=str(inquiry_id)) as traced:
        result = _orchestrate(
            traced,
            engine,
            planner,
            inquiry_id,
            inputs,
            agents=agents,
            planner_attempts=planner_attempts,
            planner_retry_delay_s=planner_retry_delay_s,
            agent_retry_delay_s=agent_retry_delay_s,
        )
    _store(engine, inquiry_id, inputs, traced.id, _status(result), result)


def orchestrate_after_checks(
    engine: Engine,
    inquiry_id: int,
    planner: Planner,
    recommender: Recommender,
    drafter: Drafter,
) -> None:
    """After a stored check result: orchestrate an exception, else drop the old orchestration.

    Runs inside the analysis and correction requests, so the planner gets a single attempt:
    a transient planner error ends in `failed` and "Re-run orchestrator" retries it.
    Never raises: unexpected errors are logged (class and inquiry id only) and leave the
    stored orchestration as it was. Then the recommendation follows the orchestration: it
    runs again, or is dropped when there is no current orchestration to recommend from.
    """
    try:
        if _drop_unless_exception(engine, inquiry_id):
            run_orchestration(engine, inquiry_id, planner, planner_attempts=1)
    except NothingToOrchestrate:
        pass  # the analysis or its checks changed meanwhile; that newer run decides
    except Exception as error:
        logger.warning("Orchestration failed for inquiry %s: %s", inquiry_id, type(error).__name__)
    recommend_after_orchestration(engine, inquiry_id, recommender, drafter)


def get_orchestration_view(session: Session, analysis: InquiryAnalysis) -> OrchestrationView | None:
    """The stored orchestration for the analysis' inquiry; None when it never ran.

    Also None when the stored result no longer matches `OrchestrationResult` (schema changed
    without a data migration): the analysis stays readable and the orchestration can be re-run.
    """
    row = session.exec(
        select(InquiryOrchestration).where(
            col(InquiryOrchestration.inquiry_id) == analysis.inquiry_id
        )
    ).first()
    if row is None:
        return None
    try:
        result = OrchestrationResult.model_validate(row.result)
    except ValidationError as error:
        # Class and inquiry id only: the validation message would quote the stored values.
        logger.error(
            "Stored orchestration result of inquiry %s does not match the schema: %s",
            analysis.inquiry_id,
            type(error).__name__,
        )
        return None
    version = analysis_version(analysis)
    checks_checked_at = session.exec(
        select(InquiryChecks.checked_at).where(
            col(InquiryChecks.inquiry_id) == analysis.inquiry_id,
            col(InquiryChecks.analysis_version) == version,
        )
    ).first()
    return OrchestrationView(
        consent=result.consent,
        planner=result.planner,
        planner_choice=result.planner_choice,
        planner_steps=result.planner_steps,
        tasks=result.tasks,
        error=result.error,
        status=row.status,
        orchestrated_at=row.orchestrated_at,
        stale=row.analysis_version != version or row.checks_checked_at != checks_checked_at,
        run=None if row.run_id is None else get_run_summary(session, row.run_id),
    )


def _read_inputs(session: Session, inquiry_id: int) -> _Inputs:
    analysis = session.exec(
        select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
    ).first()
    if analysis is None:
        raise NothingToOrchestrate
    version = analysis_version(analysis)
    checks = session.exec(
        select(InquiryChecks).where(
            col(InquiryChecks.inquiry_id) == inquiry_id,
            col(InquiryChecks.analysis_version) == version,
        )
    ).first()
    if checks is None or checks.outcome != "exception" or checks.exception_type is None:
        raise NothingToOrchestrate
    fields = ParsedFields.model_validate(analysis.fields)
    results = CheckResults.model_validate(checks.results)
    stock, customer_id = results.stock, results.customer.customer_id
    if (
        stock.product_code is None
        or stock.requested is None
        or stock.available is None
        or stock.shortage is None
        or customer_id is None
    ):
        # An exception always has a matched customer and a found product (needs_input
        # otherwise); treat a row without them as nothing to orchestrate.
        raise NothingToOrchestrate
    product_id = session.exec(
        select(Product.id).where(col(Product.code) == stock.product_code)
    ).first()
    if product_id is None:
        raise NothingToOrchestrate

    consent = substitute_consent(fields.substitute_allowed)
    facts = PlanFacts(
        exception_type=checks.exception_type,
        product_code=stock.product_code,
        requested=stock.requested,
        available=stock.available,
        shortage=stock.shortage,
        has_deadline=fields.deadline is not None,
        substitute_consent=consent,
        customer_known=True,
    )
    agent_input = AgentInput(
        customer_id=customer_id,
        product_id=product_id,
        product_code=stock.product_code,
        requested=stock.requested,
        shortage=stock.shortage,
        deadline=fields.deadline,
        reference_date=analysis.reference_date,
        consent=consent,
    )
    return _Inputs(
        version=version,
        checks_checked_at=checks.checked_at,
        facts=facts,
        agent_input=agent_input,
    )


def _orchestrate(
    traced: RunHandle,
    engine: Engine,
    planner: Planner,
    inquiry_id: int,
    inputs: _Inputs,
    *,
    agents: Sequence[AgentSpec],
    planner_attempts: int,
    planner_retry_delay_s: float,
    agent_retry_delay_s: float,
) -> OrchestrationResult:
    """Plan, validate, match and execute inside the open run; stops at the first error."""
    consent = inputs.facts.substitute_consent
    result = OrchestrationResult(consent=consent, planner=planner.name)
    choice, result.planner_steps, result.error = _plan(
        traced, planner, inquiry_id, inputs.facts, planner_attempts, planner_retry_delay_s
    )
    result.planner_choice = choice  # kept also when the plan is rejected
    if choice is None:
        return result

    with traced.step("validate-plan", kind="deterministic"):
        try:
            capabilities = validate_plan(choice, consent)
        except PlanRejected as rejected:
            # A result, not a failure: the step ends ok and the reason is stored.
            result.error = OrchestrationError(
                kind="plan_rejected", code=rejected.code, message=str(rejected)
            )
            return result

    with traced.step("match-capabilities", kind="deterministic"):
        try:
            matched = match_agents(capabilities, agents)
        except CapabilityMismatch as mismatch:
            result.error = OrchestrationError(
                kind="capability_mismatch", code=mismatch.code, message=str(mismatch)
            )
            return result

    reasons = {task.capability: task.reason for task in choice.tasks}
    plan: list[PlanItem] = [(c, matched[c], reasons[c]) for c in capabilities]
    # Every stage's thread pool is closed inside the run, so all steps are written before the
    # run finishes and its wall time covers them.
    result.tasks = execute(
        traced,
        engine,
        plan,
        inputs.agent_input,
        inquiry_id=inquiry_id,
        retry_delay_s=agent_retry_delay_s,
    )
    return result


def _plan(
    traced: RunHandle,
    planner: Planner,
    inquiry_id: int,
    facts: PlanFacts,
    attempts: int,
    retry_delay_s: float,
) -> tuple[PlannerChoice | None, list[str], OrchestrationError | None]:
    """The planner's choice; a transient error is retried as step `plan#2` while attempts remain."""
    steps: list[str] = []
    for attempt in range(1, attempts + 1):
        name = "plan" if attempt == 1 else f"plan#{attempt}"
        steps.append(name)
        try:
            with traced.step(name, kind=planner.step_kind) as step:
                try:
                    planning = planner.plan(facts)
                except PlannerError as error:
                    # The provider may have billed the call before it failed.
                    if error.usage is not None:
                        step.record_usage(error.usage)
                    raise
                if planning.usage is not None:
                    step.record_usage(planning.usage)
        except PlannerError as error:
            if error.transient and attempt < attempts:
                time.sleep(retry_delay_s)
                continue
            logger.warning(
                "Orchestration of inquiry %s: %s failed with %s",
                inquiry_id,
                name,
                type(error).__name__,
            )
            return (
                None,
                steps,
                OrchestrationError(
                    kind="planner_failed", code=_planner_error_code(error), message=str(error)
                ),
            )
        return planning.choice, steps, None
    raise AssertionError("unreachable")  # pragma: no cover


def _planner_error_code(error: PlannerError) -> str:
    if isinstance(error, PlannerNotConfigured):
        return "not_configured"
    if isinstance(error, PlannerRateLimited):
        return "rate_limited"
    if isinstance(error, PlannerFailed) and error.transient:
        return "unavailable"
    return "failed"


def _status(result: OrchestrationResult) -> OrchestrationStatus:
    if result.error is not None:
        return "failed"
    if any(task.status != "completed" for task in result.tasks):
        return "partial"
    return "completed"


def _store(
    engine: Engine,
    inquiry_id: int,
    inputs: _Inputs,
    run_id: int | None,
    status: OrchestrationStatus,
    result: OrchestrationResult,
) -> None:
    values: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "run_id": run_id,
        "analysis_version": inputs.version,
        "checks_checked_at": inputs.checks_checked_at,
        "status": status,
        "result": result.model_dump(mode="json"),
        "orchestrated_at": datetime.now(UTC),
    }
    statement = insert(InquiryOrchestration).values(values)
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
        session.exec(statement)
        session.commit()


def _drop_unless_exception(engine: Engine, inquiry_id: int) -> bool:
    """True when the current check result is an exception (so it should be orchestrated).

    When the current analysis version has another outcome, its orchestration and the
    recommendation made from it are deleted. Without a check result for the current version
    nothing changes (the stored orchestration is shown as stale).
    """
    with Session(engine) as session:
        analysis = lock_analysis(session, inquiry_id)
        if analysis is None:
            return False
        checks = current_checks(session, inquiry_id, analysis_version(analysis))
        if checks is not None and checks.outcome == "exception":
            return True
        if checks is not None:
            session.exec(
                delete(InquiryOrchestration).where(
                    col(InquiryOrchestration.inquiry_id) == inquiry_id
                )
            )
            session.exec(
                delete(InquiryRecommendation).where(
                    col(InquiryRecommendation.inquiry_id) == inquiry_id
                )
            )
            session.commit()
        return False
