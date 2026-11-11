import threading
from collections.abc import Callable, Iterator
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

from app.orchestration.agents import AgentInput
from app.orchestration.executor import PlanItem, execute
from app.orchestration.planning import (
    PlannerError,
    PlannerFailed,
    PlannerNotConfigured,
    PlannerRateLimited,
    PlanRejected,
    RuleBasedPlanner,
    stages,
    substitute_consent,
    validate_plan,
)
from app.orchestration.registry import (
    AGENTS,
    CAPABILITIES,
    AgentSpec,
    CapabilityMismatch,
    match_agents,
)
from app.orchestration.schema import (
    AgentResult,
    Capability,
    CustomerHistoryResult,
    OrchestrationResult,
    PlanFacts,
    PlannedTask,
    PlannerChoice,
    SubstituteAvailabilityResult,
    SubstituteCompatibilityResult,
    SubstituteConsent,
    SupplierAvailabilityResult,
    TaskOutcome,
)
from app.tracing import RunHandle, run
from app.tracing.models import TraceRun, TraceStep
from tests.conftest import TEST_SUBJECT_TYPE

ALL: list[Capability] = list(CAPABILITIES)
NO_SUBSTITUTE: list[Capability] = ["supplier-availability", "customer-history"]


def _choice(*capabilities: Capability) -> PlannerChoice:
    return PlannerChoice(
        tasks=[PlannedTask(capability=c, reason="test") for c in capabilities], summary="test"
    )


def _facts(consent: SubstituteConsent, *, has_deadline: bool = True) -> PlanFacts:
    return PlanFacts(
        exception_type="insufficient_stock",
        product_code="ABC-100",
        requested=80,
        available=50,
        shortage=30,
        has_deadline=has_deadline,
        substitute_consent=consent,
        customer_known=True,
    )


# --- Registry -------------------------------------------------------------------------


def test_capability_graph_is_acyclic() -> None:
    visiting: set[Capability] = set()
    done: set[Capability] = set()

    def visit(capability: Capability) -> None:
        assert capability not in visiting, f"cycle through {capability}"
        if capability in done:
            return
        visiting.add(capability)
        for prerequisite in CAPABILITIES[capability].depends_on:
            assert prerequisite in CAPABILITIES
            visit(prerequisite)
        visiting.remove(capability)
        done.add(capability)

    for capability in CAPABILITIES:
        visit(capability)


def test_registry_keys_match_spec_names_and_the_only_edge() -> None:
    assert all(name == spec.name for name, spec in CAPABILITIES.items())
    edges = {(c, p) for c, spec in CAPABILITIES.items() for p in spec.depends_on}
    assert edges == {("substitute-availability", "substitute-compatibility")}


def test_every_capability_has_exactly_one_agent() -> None:
    matched = match_agents(ALL)

    assert {c: a.name for c, a in matched.items()} == {
        "substitute-compatibility": "catalog-agent",
        "substitute-availability": "warehouse-agent",
        "supplier-availability": "supplier-agent",
        "customer-history": "history-agent",
    }
    for capability in ALL:
        assert sum(capability in a.capabilities for a in AGENTS) == 1


def test_match_agents_without_agent_is_no_agent() -> None:
    partial = tuple(a for a in AGENTS if "customer-history" not in a.capabilities)

    with pytest.raises(CapabilityMismatch) as raised:
        match_agents(ALL, partial)

    assert (raised.value.code, raised.value.capability) == ("no_agent", "customer-history")


def test_match_agents_with_two_agents_is_ambiguous() -> None:
    twin = AgentSpec(name="twin", capabilities=("supplier-availability",), run=AGENTS[2].run)

    with pytest.raises(CapabilityMismatch) as raised:
        match_agents(NO_SUBSTITUTE, (*AGENTS, twin))

    assert (raised.value.code, raised.value.capability) == (
        "ambiguous_agent",
        "supplier-availability",
    )


# --- Validation -----------------------------------------------------------------------


@pytest.mark.parametrize("consent", ["confirmed", "unconfirmed"])
def test_full_plan_is_valid(consent: SubstituteConsent) -> None:
    assert validate_plan(_choice(*ALL), consent) == ALL


def test_plan_without_substitutes_is_valid_when_refused() -> None:
    assert validate_plan(_choice(*NO_SUBSTITUTE), "refused") == NO_SUBSTITUTE


@pytest.mark.parametrize(
    ("capabilities", "consent", "code"),
    [
        ((), "confirmed", "empty_plan"),
        ((*ALL, "customer-history"), "confirmed", "too_many_tasks"),
        (("customer-history", "customer-history"), "confirmed", "duplicate_capability"),
        (("supplier-availability", "substitute-compatibility"), "refused", "substitute_refused"),
        (("substitute-availability",), "confirmed", "missing_prerequisite"),
        # The first broken rule wins: duplicates before refusal, refusal before prerequisites.
        (("substitute-availability", "substitute-availability"), "refused", "duplicate_capability"),
        (("substitute-availability",), "refused", "substitute_refused"),
    ],
)
def test_plan_rejection_codes(
    capabilities: tuple[Capability, ...], consent: SubstituteConsent, code: str
) -> None:
    with pytest.raises(PlanRejected) as raised:
        validate_plan(_choice(*capabilities), consent)

    assert raised.value.code == code


# --- Planner --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("allowed", "consent"), [(True, "confirmed"), (False, "refused"), (None, "unconfirmed")]
)
def test_substitute_consent_from_parsed_field(
    allowed: bool | None, consent: SubstituteConsent
) -> None:
    assert substitute_consent(allowed) == consent


@pytest.mark.parametrize(
    ("consent", "expected"),
    [("confirmed", ALL), ("unconfirmed", ALL), ("refused", NO_SUBSTITUTE)],
)
def test_rule_based_planner_plans_by_consent(
    consent: SubstituteConsent, expected: list[Capability]
) -> None:
    planner = RuleBasedPlanner()
    result = planner.plan(_facts(consent))

    assert (planner.name, planner.step_kind) == ("fake", "deterministic")
    assert result.usage is None
    assert [t.capability for t in result.choice.tasks] == expected
    assert validate_plan(result.choice, consent) == expected
    assert "30" in result.choice.summary
    assert all(t.reason for t in result.choice.tasks)


def test_rule_based_planner_reasons_are_fixed_sentences_with_facts() -> None:
    choice = RuleBasedPlanner().plan(_facts("confirmed", has_deadline=False)).choice
    reasons = {t.capability: t.reason for t in choice.tasks}

    assert reasons["substitute-compatibility"] == (
        "ABC-100 is short by 30 pcs; look for compatible substitutes."
    )
    assert (
        reasons["supplier-availability"]
        == "Check whether a supplier can deliver 30 pcs of ABC-100."
    )
    assert RuleBasedPlanner().plan(_facts("confirmed", has_deadline=False)).choice == choice


def test_planner_errors_carry_transience_and_usage() -> None:
    assert PlannerRateLimited("429").transient
    assert not PlannerNotConfigured("no key").transient
    assert PlannerFailed("timeout", transient=True).transient
    assert not PlannerFailed("bad schema", transient=False).transient
    assert all(
        issubclass(c, PlannerError)
        for c in (PlannerNotConfigured, PlannerRateLimited, PlannerFailed)
    )
    assert PlannerError("x").usage is None


# --- Stages ---------------------------------------------------------------------------


def test_stages_of_full_plan() -> None:
    planned: list[Capability] = [
        "customer-history",
        "substitute-availability",
        "supplier-availability",
        "substitute-compatibility",
    ]

    assert stages(planned) == [
        ["substitute-compatibility", "supplier-availability", "customer-history"],
        ["substitute-availability"],
    ]


def test_stages_of_plan_without_substitute() -> None:
    assert stages(["customer-history", "supplier-availability"]) == [
        ["supplier-availability", "customer-history"]
    ]


def test_result_round_trips_through_json() -> None:
    result = OrchestrationResult(
        consent="confirmed",
        planner="fake",
        planner_choice=_choice(*ALL),
        planner_steps=["plan"],
        tasks=[
            TaskOutcome(
                capability="customer-history",
                agent="history-agent",
                reason="r",
                depends_on=[],
                stage=1,
                status="completed",
                steps=["agent:customer-history"],
                result=_HISTORY,
            )
        ],
    )

    assert OrchestrationResult.model_validate(result.model_dump(mode="json")) == result


# --- Executor -------------------------------------------------------------------------

_COMPATIBILITY = SubstituteCompatibilityResult(candidates=[])
_AVAILABILITY = SubstituteAvailabilityResult(candidates=[])
_SUPPLIER = SupplierAvailabilityResult(offers=[])
_HISTORY = CustomerHistoryResult(
    orders_count=0, substitutes_offered=0, substitutes_accepted=0, signal="no_substitute_history"
)
_RESULTS: dict[Capability, AgentResult] = {
    "substitute-compatibility": _COMPATIBILITY,
    "substitute-availability": _AVAILABILITY,
    "supplier-availability": _SUPPLIER,
    "customer-history": _HISTORY,
}
_INPUT = AgentInput(
    customer_id=1,
    product_id=1,
    product_code="ABC-100",
    requested=80,
    shortage=30,
    deadline=date(2026, 11, 6),
    reference_date=date(2026, 11, 2),
    consent="confirmed",
)

AgentRun = Callable[[Engine, AgentInput], AgentResult]


class FlakyError(Exception):
    pass


def _operational_error() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("connection lost"))


def _returns(capability: Capability) -> AgentRun:
    def run_agent(engine: Engine, agent_input: AgentInput) -> AgentResult:
        return _RESULTS[capability]

    return run_agent


def _plan(runs: dict[Capability, AgentRun]) -> list[PlanItem]:
    return [
        (c, AgentSpec(name=f"{c}-stub", capabilities=(c,), run=r), f"reason {c}")
        for c, r in runs.items()
    ]


@pytest.fixture(autouse=True)
def _delete_test_runs(migrated_engine: Engine) -> Iterator[None]:
    yield
    with Session(migrated_engine) as session:
        session.exec(delete(TraceRun).where(col(TraceRun.subject_type) == TEST_SUBJECT_TYPE))
        session.commit()


def _execute(engine: Engine, plan: list[PlanItem]) -> tuple[list[TaskOutcome], list[TraceStep]]:
    with run(engine, subject_type=TEST_SUBJECT_TYPE, subject_id=f"test-{uuid4()}") as traced:
        outcomes = execute(traced, engine, plan, _INPUT, retry_delay_s=0)
    return outcomes, _steps(engine, traced)


def _steps(engine: Engine, traced: RunHandle) -> list[TraceStep]:
    assert traced.id is not None
    with Session(engine) as session:
        statement = (
            select(TraceStep).where(TraceStep.run_id == traced.id).order_by(col(TraceStep.id))
        )
        return list(session.exec(statement).all())


def _by_capability(outcomes: list[TaskOutcome]) -> dict[Capability, TaskOutcome]:
    return {o.capability: o for o in outcomes}


def test_execute_runs_stages_in_order_and_passes_upstream(migrated_engine: Engine) -> None:
    seen_upstream: list[dict[Capability, AgentResult]] = []

    def warehouse(engine: Engine, agent_input: AgentInput) -> AgentResult:
        seen_upstream.append(dict(agent_input.upstream))
        return _AVAILABILITY

    runs: dict[Capability, AgentRun] = {c: _returns(c) for c in ALL}
    runs["substitute-availability"] = warehouse

    outcomes, steps = _execute(migrated_engine, _plan(runs))

    assert [(o.capability, o.stage, o.status) for o in outcomes] == [
        ("substitute-compatibility", 1, "completed"),
        ("supplier-availability", 1, "completed"),
        ("customer-history", 1, "completed"),
        ("substitute-availability", 2, "completed"),
    ]
    assert seen_upstream == [{"substitute-compatibility": _COMPATIBILITY}]
    by_capability = _by_capability(outcomes)
    assert by_capability["substitute-availability"].depends_on == ["substitute-compatibility"]
    assert by_capability["substitute-availability"].agent == "substitute-availability-stub"
    assert by_capability["customer-history"].reason == "reason customer-history"
    assert by_capability["customer-history"].result == _HISTORY
    assert all(o.steps == [f"agent:{o.capability}"] for o in outcomes)
    assert sorted(s.name for s in steps) == sorted(f"agent:{c}" for c in ALL)
    assert all(s.kind == "deterministic" and s.status == "ok" for s in steps)
    assert steps[-1].name == "agent:substitute-availability"


def test_execute_runs_a_stage_in_parallel(migrated_engine: Engine) -> None:
    barrier = threading.Barrier(2, timeout=5)

    def waits(capability: Capability) -> AgentRun:
        def run_agent(engine: Engine, agent_input: AgentInput) -> AgentResult:
            barrier.wait()  # passes only when both tasks run at the same time
            return _RESULTS[capability]

        return run_agent

    outcomes, _ = _execute(migrated_engine, _plan({c: waits(c) for c in NO_SUBSTITUTE}))

    assert [o.status for o in outcomes] == ["completed", "completed"]


def test_execute_retries_a_transient_error_once(migrated_engine: Engine) -> None:
    calls: list[int] = []

    def flaky(engine: Engine, agent_input: AgentInput) -> AgentResult:
        calls.append(1)
        if len(calls) == 1:
            raise _operational_error()
        return _SUPPLIER

    outcomes, steps = _execute(migrated_engine, _plan({"supplier-availability": flaky}))

    [outcome] = outcomes
    assert outcome.status == "completed"
    assert outcome.steps == ["agent:supplier-availability", "agent:supplier-availability#2"]
    assert outcome.result == _SUPPLIER
    assert [(s.name, s.status, s.error_type) for s in steps] == [
        ("agent:supplier-availability", "failed", "OperationalError"),
        ("agent:supplier-availability#2", "ok", None),
    ]


def test_execute_fails_after_second_transient_error(migrated_engine: Engine) -> None:
    def down(engine: Engine, agent_input: AgentInput) -> AgentResult:
        raise _operational_error()

    outcomes, steps = _execute(migrated_engine, _plan({"customer-history": down}))

    [outcome] = outcomes
    assert (outcome.status, outcome.error_type, outcome.result) == (
        "failed",
        "OperationalError",
        None,
    )
    assert len(outcome.steps) == 2
    assert [s.status for s in steps] == ["failed", "failed"]


def test_execute_does_not_retry_other_errors(migrated_engine: Engine) -> None:
    calls: list[int] = []

    def broken(engine: Engine, agent_input: AgentInput) -> AgentResult:
        calls.append(1)
        raise FlakyError

    outcomes, steps = _execute(migrated_engine, _plan({"customer-history": broken}))

    [outcome] = outcomes
    assert (outcome.status, outcome.error_type) == ("failed", "FlakyError")
    assert outcome.steps == ["agent:customer-history"]
    assert len(calls) == 1
    assert [(s.name, s.status, s.error_type) for s in steps] == [
        ("agent:customer-history", "failed", "FlakyError")
    ]


def test_execute_rejects_a_result_of_another_capability(migrated_engine: Engine) -> None:
    outcomes, _ = _execute(
        migrated_engine, _plan({"customer-history": _returns("supplier-availability")})
    )

    [outcome] = outcomes
    assert (outcome.status, outcome.error_type) == ("failed", "UnexpectedResult")


def test_failed_prerequisite_skips_dependent_only(migrated_engine: Engine) -> None:
    def broken(engine: Engine, agent_input: AgentInput) -> AgentResult:
        raise FlakyError

    runs: dict[Capability, AgentRun] = {c: _returns(c) for c in ALL}
    runs["substitute-compatibility"] = broken

    outcomes, steps = _execute(migrated_engine, _plan(runs))

    by_capability = _by_capability(outcomes)
    assert by_capability["substitute-compatibility"].status == "failed"
    skipped = by_capability["substitute-availability"]
    assert (skipped.status, skipped.steps, skipped.stage, skipped.result) == (
        "skipped",
        [],
        2,
        None,
    )
    assert by_capability["supplier-availability"].status == "completed"
    assert by_capability["customer-history"].status == "completed"
    assert "agent:substitute-availability" not in {s.name for s in steps}
