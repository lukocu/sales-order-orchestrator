"""Scoring of evaluation runs on hand-built analysis views: observe, score, summarize and
instability. No database."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.checks.schema import (
    CheckResults,
    CreditCheck,
    CustomerCheck,
    DiscountCheck,
    Outcome,
    PriceCheck,
    StockCheck,
)
from app.checks.service import ChecksView
from app.eval.cases import EvalCase
from app.eval.scoring import (
    ArmName,
    ArmRun,
    Observation,
    instability,
    observe,
    score,
    summarize,
)
from app.orchestration.schema import OrchestrationError, OrchestrationStatus
from app.orchestration.service import OrchestrationView
from app.parsing.service import AnalysisView
from app.policy.schema import PolicyOutcome
from app.policy.service import PolicyView
from app.recommendation.schema import (
    OptionKind,
    RecommendationError,
    RecommendationOption,
    RecommenderChoice,
)
from app.recommendation.service import RecommendationView
from app.tracing.summary import RunSummary, RunTotals

AT = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
FIELDS: dict[str, Any] = {
    "customer": "ACME",
    "product_code": "ABC-100",
    "quantity": 80,
    "deadline": None,
    "deadline_text": None,
    "substitute_allowed": True,
    "price_kind": "none",
    "price_value": None,
    "price_text": None,
}


# --- Builders ---------------------------------------------------------------------------


def _run(
    run_id: int,
    *,
    cost: str = "0",
    complete: bool = True,
    duration_ms: float | None = 100.0,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> RunSummary:
    return RunSummary(
        id=run_id,
        subject_type="inquiry",
        subject_id="1",
        status="completed",
        started_at=AT,
        duration_ms=duration_ms,
        steps=[],
        totals=RunTotals(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=0,
            cost_usd=Decimal(cost),
            cost_complete=complete,
            steps_duration_ms=duration_ms or 0.0,
            duration_ms=duration_ms,
        ),
    )


def _checks(outcome: Outcome) -> ChecksView:
    return ChecksView(
        outcome=outcome,
        exception_type="insufficient_stock" if outcome == "exception" else None,
        reasons=["quantity_missing"] if outcome == "needs_input" else [],
        results=CheckResults(
            customer=CustomerCheck(status="matched"),
            stock=StockCheck(status="insufficient" if outcome == "exception" else "ok"),
            price=PriceCheck(status="skipped"),
            discount=DiscountCheck(status="skipped"),
            credit=CreditCheck(status="skipped"),
        ),
        checked_at=AT,
        stale=False,
        uncertain_inputs=[],
        run=_run(90),
    )


def _orchestration(
    status: OrchestrationStatus = "completed",
    *,
    error_code: str | None = None,
    run: RunSummary | None = None,
) -> OrchestrationView:
    error = (
        None
        if error_code is None
        else OrchestrationError(kind="planner_failed", code=error_code, message="failed")
    )
    return OrchestrationView(
        consent="confirmed",
        planner="groq",
        error=error,
        status=status,
        orchestrated_at=AT,
        stale=False,
        run=run,
    )


def _option(option_id: str, kind: OptionKind) -> RecommendationOption:
    return RecommendationOption(
        id=option_id,
        kind=kind,
        lines=[],
        covered_quantity=80,
        requested_quantity=80,
        fulfilled_on=date(2026, 11, 2),
        meets_deadline=None,
        value=Decimal("9262.50"),
        cost=Decimal("6900.00"),
        margin_percent=Decimal("25.51"),
        band="HIGH" if kind == "substitute" else "LOW",
        signals=[],
    )


OPTIONS = [
    _option("stock", "partial_delivery"),
    _option("stock+ABC-110", "substitute"),
    _option("stock+supplier:Sensortech Polska", "other_source"),
]


def _recommendation(
    option_id: str | None = "stock+ABC-110",
    *,
    error: RecommendationError | None = None,
    run: RunSummary | None = None,
) -> RecommendationView:
    choice = (
        None
        if option_id is None
        else RecommenderChoice(option_id=option_id, justification="Wybrano.", cited_signals=[])
    )
    return RecommendationView(
        recommender="groq",
        options=OPTIONS,
        choice=choice,
        error=error,
        status="failed"
        if error is not None and error.kind == "recommender_failed"
        else "completed",
        recommended_at=AT,
        stale=False,
        run=run,
    )


def _policy(outcome: PolicyOutcome = "no_approval_needed", *, run: RunSummary | None) -> PolicyView:
    return PolicyView(
        option_id="stock+ABC-110",
        rules=[],
        outcome=outcome,
        thresholds_are_examples=True,
        evaluated_at=AT,
        stale=False,
        run=run,
    )


def _view(
    outcome: Outcome = "exception",
    *,
    orchestration: OrchestrationView | None = None,
    recommendation: RecommendationView | None = None,
    policy: PolicyView | None = None,
) -> AnalysisView:
    return AnalysisView.model_validate(
        {
            "inquiry_id": 1,
            "extractor": "fake",
            "reference_date": date(2026, 11, 2),
            "fields": FIELDS,
            "model_fields": FIELDS,
            "uncertain": {},
            "corrected_fields": [],
            "analyzed_at": AT,
            "analyzed_by_name": None,
            "corrected_at": AT,
            "corrected_by_name": None,
            "run": None,
            "checks": _checks(outcome),
            "orchestration": orchestration,
            "recommendation": recommendation,
            "policy": policy,
            "draft": None,
            "decisions": [],
        }
    )


def _full_view(
    *,
    option_id: str = "stock+ABC-110",
    policy_outcome: PolicyOutcome = "no_approval_needed",
    status: OrchestrationStatus = "completed",
) -> AnalysisView:
    return _view(
        orchestration=_orchestration(
            status, run=_run(1, cost="0.0012", duration_ms=1500.4, input_tokens=300)
        ),
        recommendation=_recommendation(
            option_id, run=_run(2, cost="0.0008", duration_ms=900.3, output_tokens=120)
        ),
        policy=_policy(policy_outcome, run=_run(3, duration_ms=10.2)),
    )


def _case(
    outcome: Outcome = "exception",
    option_kind: OptionKind | None = "substitute",
    policy_outcome: PolicyOutcome | None = "no_approval_needed",
    case_id: str = "acme-test",
) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": case_id,
            "sender_name": "Marek Nowak",
            "sender_email": "zakupy@acme.example",
            "subject": "Zapytanie",
            "body": "Dzień dobry",
            "received_at": AT,
            "fields": FIELDS,
            "expected": {
                "checks_outcome": outcome,
                "option_kind": option_kind,
                "policy_outcome": policy_outcome,
            },
            "rationale": "Test.",
        }
    )


def _observation(**overrides: Any) -> Observation:
    values: dict[str, Any] = {
        "checks_outcome": "exception",
        "option_kind": "substitute",
        "policy_outcome": "no_approval_needed",
        "band": "HIGH",
        "failure": None,
        "cost_usd": Decimal("0.001"),
        "cost_complete": True,
        "duration_ms": 1000,
        "input_tokens": 100,
        "output_tokens": 50,
    }
    return Observation.model_validate(values | overrides)


def _arm_run(
    case: EvalCase, obs: Observation, *, arm: ArmName = "orchestrator", repeat: int = 1
) -> ArmRun:
    return ArmRun(case_id=case.id, arm=arm, repeat=repeat, observation=obs, score=score(case, obs))


# --- observe ----------------------------------------------------------------------------


def test_observe_a_completed_chain_sums_the_three_stage_runs() -> None:
    obs = observe(_full_view())
    assert obs.checks_outcome == "exception"
    assert obs.option_kind == "substitute"  # resolved from choice.option_id
    assert obs.band == "HIGH"
    assert obs.policy_outcome == "no_approval_needed"
    assert obs.failure is None
    assert obs.cost_usd == Decimal("0.0020")
    assert obs.cost_complete is True
    assert obs.duration_ms == 2411  # 1500.4 + 900.3 + 10.2, rounded
    assert (obs.input_tokens, obs.output_tokens) == (300, 120)


def test_observe_an_unpriced_step_makes_the_cost_incomplete() -> None:
    view = _full_view()
    assert view.recommendation is not None
    view.recommendation.run = _run(2, cost="0", complete=False)
    assert observe(view).cost_complete is False


def test_observe_a_failed_orchestration() -> None:
    view = _view(
        orchestration=_orchestration(
            "failed", error_code="rate_limited", run=_run(1, cost="0.0003", input_tokens=40)
        )
    )
    obs = observe(view)
    assert obs.failure == "orchestration_failed:rate_limited"
    assert (obs.option_kind, obs.policy_outcome, obs.band) == (None, None, None)
    # The billed planner attempt is counted; nothing else was expected to run.
    assert obs.cost_usd == Decimal("0.0003")
    assert obs.cost_complete is True
    assert obs.input_tokens == 40


def test_observe_a_partial_orchestration_keeps_the_decision() -> None:
    obs = observe(_full_view(status="partial"))
    assert obs.failure == "orchestration_partial"
    assert obs.option_kind == "substitute"
    assert score(_case(), obs).full_hit is True  # noted, not a miss


def test_observe_a_failed_recommender() -> None:
    error = RecommendationError(kind="recommender_failed", code="rate_limited", message="429")
    view = _view(
        orchestration=_orchestration(run=_run(1)),
        recommendation=_recommendation(None, error=error, run=_run(2)),
    )
    obs = observe(view)
    assert obs.failure == "recommender_failed:rate_limited"
    assert (obs.option_kind, obs.policy_outcome) == (None, None)
    assert obs.cost_complete is True


def test_observe_a_rejected_choice() -> None:
    error = RecommendationError(kind="choice_rejected", code="unknown_option", message="no")
    view = _view(
        orchestration=_orchestration(run=_run(1)),
        recommendation=_recommendation(None, error=error, run=_run(2)),
    )
    obs = observe(view)
    assert obs.failure == "choice_rejected"
    assert obs.option_kind is None


def test_observe_a_missing_stage_run_keeps_the_decision_but_not_the_cost() -> None:
    view = _full_view()
    assert view.policy is not None
    view.policy.run = None
    obs = observe(view)
    assert obs.failure == "missing_run"
    assert obs.cost_complete is False
    assert obs.cost_usd == Decimal("0.0020")
    assert (obs.option_kind, obs.policy_outcome) == ("substitute", "no_approval_needed")
    assert score(_case(), obs).full_hit is True


def test_observe_a_missing_stage_is_a_missing_run() -> None:
    view = _view(
        orchestration=_orchestration(run=_run(1)), recommendation=_recommendation(run=_run(2))
    )
    obs = observe(view)
    assert obs.failure == "missing_run"
    assert obs.cost_complete is False
    assert obs.policy_outcome is None
    assert score(_case(), obs).full_hit is False


def test_observe_without_an_orchestration_for_an_exception() -> None:
    obs = observe(_view())
    assert obs.failure == "missing_run"
    assert obs.cost_complete is False
    assert obs.cost_usd == Decimal(0)


def test_observe_a_non_exception_has_no_stages_and_no_cost() -> None:
    obs = observe(_view("standard"))
    assert obs.checks_outcome == "standard"
    assert obs.failure is None
    assert (obs.option_kind, obs.policy_outcome, obs.band) == (None, None, None)
    assert obs.cost_usd == Decimal(0)
    assert obs.cost_complete is True
    assert obs.duration_ms == 0


# --- score ------------------------------------------------------------------------------


def test_score_a_hit() -> None:
    result = score(_case(), observe(_full_view()))
    assert (result.checks_hit, result.option_hit, result.policy_hit, result.full_hit) == (
        True,
        True,
        True,
        True,
    )


def test_score_an_option_miss() -> None:
    result = score(_case(), observe(_full_view(option_id="stock+supplier:Sensortech Polska")))
    assert (result.option_hit, result.policy_hit, result.full_hit) == (False, True, False)


def test_score_a_verdict_miss() -> None:
    result = score(_case(), observe(_full_view(policy_outcome="requires_supervisor")))
    assert (result.option_hit, result.policy_hit, result.full_hit) == (True, False, False)


@pytest.mark.parametrize(
    "failure",
    [
        "orchestration_failed:rate_limited",
        "recommender_failed:unavailable",
        "choice_rejected",
        "missing_run",
    ],
)
def test_score_a_failure_without_a_decision_misses_everything(failure: str) -> None:
    obs = _observation(failure=failure, option_kind=None, policy_outcome=None, band=None)
    result = score(_case(), obs)
    assert result.checks_hit is True
    assert (result.option_hit, result.policy_hit, result.full_hit) == (False, False, False)


def test_score_a_non_exception_case_only_by_its_checks() -> None:
    case = _case("standard", None, None)
    hit = score(case, observe(_view("standard")))
    assert (hit.checks_hit, hit.option_hit, hit.policy_hit, hit.full_hit) == (
        True,
        None,
        None,
        True,
    )
    miss = score(case, observe(_view("needs_input")))
    assert (miss.checks_hit, miss.full_hit) == (False, False)


def test_score_an_exception_label_against_another_checks_outcome() -> None:
    result = score(_case(), observe(_view("standard")))
    assert (result.checks_hit, result.option_hit, result.policy_hit, result.full_hit) == (
        False,
        False,
        False,
        False,
    )


# --- summarize --------------------------------------------------------------------------


def test_summarize_one_arm() -> None:
    exception = _case(case_id="exception-case")
    standard = _case("standard", None, None, case_id="standard-case")
    runs = [
        _arm_run(exception, _observation(cost_usd=Decimal("0.003"), duration_ms=1000), repeat=1),
        _arm_run(
            exception,
            _observation(
                option_kind="other_source",
                failure="orchestration_partial",
                cost_usd=Decimal("0.002"),
                duration_ms=2000,
            ),
            repeat=2,
        ),
        _arm_run(
            exception,
            _observation(
                option_kind=None,
                policy_outcome=None,
                band=None,
                failure="orchestration_failed:rate_limited",
                cost_usd=Decimal("0.001"),
                cost_complete=False,
                duration_ms=600,
                input_tokens=10,
                output_tokens=0,
            ),
            repeat=3,
        ),
        _arm_run(
            standard,
            _observation(
                checks_outcome="standard",
                option_kind=None,
                policy_outcome=None,
                band=None,
                cost_usd=Decimal(0),
                duration_ms=0,
                input_tokens=0,
                output_tokens=0,
            ),
        ),
    ]
    summary = summarize(runs)
    assert summary.arm == "orchestrator"
    assert summary.runs == 4
    assert (summary.full.hits, summary.full.total) == (2, 4)
    assert summary.full.rate == 0.5
    # The standard case is not in the component denominators.
    assert (summary.option.hits, summary.option.total) == (1, 3)
    assert (summary.policy.hits, summary.policy.total) == (2, 3)
    assert (summary.checks.hits, summary.checks.total) == (4, 4)
    assert summary.failures == {"orchestration_failed:rate_limited": 1, "orchestration_partial": 1}
    assert summary.cost_usd_total == Decimal("0.006")
    assert summary.cost_usd_mean == Decimal("0.0015000000")
    assert summary.cost_complete is False
    assert summary.duration_ms_mean == 900.0
    assert summary.duration_ms_max == 2000
    assert (summary.input_tokens, summary.output_tokens) == (210, 100)


def test_summarize_rate_is_none_without_scored_runs() -> None:
    standard = _case("standard", None, None)
    obs = _observation(checks_outcome="standard", option_kind=None, policy_outcome=None)
    summary = summarize([_arm_run(standard, obs, arm="workflow")])
    assert summary.arm == "workflow"
    assert summary.option.total == 0
    assert summary.option.rate is None
    assert summary.cost_complete is True
    assert summary.failures == {}


def test_summarize_rejects_no_runs_and_mixed_arms() -> None:
    with pytest.raises(ValueError):
        summarize([])
    case = _case()
    runs = [
        _arm_run(case, _observation(), arm="workflow"),
        _arm_run(case, _observation(), arm="orchestrator"),
    ]
    with pytest.raises(ValueError):
        summarize(runs)


# --- instability ------------------------------------------------------------------------


def test_instability_lists_cases_whose_repeats_disagree() -> None:
    steady = _case(case_id="steady-case")
    shaky = _case(case_id="shaky-case")
    runs = [
        _arm_run(steady, _observation(), arm="orchestrator", repeat=1),
        _arm_run(steady, _observation(), arm="orchestrator", repeat=2),
        # Same decision, different cost and failure note: still stable.
        _arm_run(
            steady,
            _observation(failure="orchestration_partial", cost_usd=Decimal("0.5")),
            arm="orchestrator",
            repeat=3,
        ),
        _arm_run(shaky, _observation(), arm="workflow", repeat=1),
        _arm_run(shaky, _observation(), arm="workflow", repeat=2),
        _arm_run(shaky, _observation(), arm="orchestrator", repeat=2),
        _arm_run(
            shaky,
            _observation(option_kind="other_source", policy_outcome="requires_supervisor"),
            arm="orchestrator",
            repeat=1,
        ),
    ]
    (unstable,) = instability(runs)
    assert (unstable.case_id, unstable.arm) == ("shaky-case", "orchestrator")
    assert [d.repeat for d in unstable.decisions] == [1, 2]
    assert [d.option_kind for d in unstable.decisions] == ["other_source", "substitute"]


def test_instability_counts_a_failure_without_a_decision_as_a_different_decision() -> None:
    case = _case()
    runs = [
        _arm_run(case, _observation(), repeat=1),
        _arm_run(
            case,
            _observation(
                option_kind=None,
                policy_outcome=None,
                failure="recommender_failed:rate_limited",
            ),
            repeat=2,
        ),
    ]
    assert [u.case_id for u in instability(runs)] == ["acme-test"]
