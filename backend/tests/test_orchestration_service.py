from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

from app.inquiries.models import Inquiry
from app.orchestration.agents import AgentInput
from app.orchestration.models import InquiryOrchestration
from app.orchestration.planning import (
    PlannerFailed,
    PlanningResult,
    RuleBasedPlanner,
)
from app.orchestration.registry import AGENTS, AgentSpec
from app.orchestration.schema import AgentResult, PlanFacts
from app.orchestration.service import run_orchestration
from app.parsing.models import InquiryAnalysis
from app.tracing.models import StepKind, TraceRun
from tests.conftest import ExtractorSetter, InquiryFactory
from tests.test_parsing_extractors import ACME, BIURO_MAX, DELTA, OMEGA

# Run-level tolerance for the step writes between steps, which the steps do not time.
WALL_TIME_TOLERANCE_MS = 250.0
FULL_PLAN_STAGES = [
    ("substitute-compatibility", 1),
    ("supplier-availability", 1),
    ("customer-history", 1),
    ("substitute-availability", 2),
]


def _analysis_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/analysis"


def _checks_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/checks"


def _inquiry(make_inquiry: InquiryFactory, seed: tuple[str, str, date]) -> Inquiry:
    subject, body, reference = seed
    return make_inquiry(
        received_at=datetime(reference.year, reference.month, reference.day, 9, 0, tzinfo=UTC),
        subject=subject,
        body=body,
    )


@pytest.fixture
def acme(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, ACME)


@pytest.fixture
def omega(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, OMEGA)


@pytest.fixture
def delta(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, DELTA)


@pytest.fixture
def biuro_max(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, BIURO_MAX)


def _analyze(client: TestClient, inquiry: Inquiry) -> dict[str, Any]:
    response = client.post(_analysis_path(inquiry.id))
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def _orchestration(client: TestClient, inquiry: Inquiry) -> dict[str, Any] | None:
    view: dict[str, Any] | None = client.get(_analysis_path(inquiry.id)).json()["orchestration"]
    return view


def _correct(client: TestClient, analysis: dict[str, Any], **changes: Any) -> dict[str, Any]:
    response = client.put(
        _analysis_path(analysis["inquiry_id"]),
        json={
            "fields": {**analysis["fields"], **changes},
            "reviewed": [],
            "analyzed_at": analysis["analyzed_at"],
        },
    )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def _tasks(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {task["capability"]: task for task in view["tasks"]}


def _stages(view: dict[str, Any]) -> list[tuple[str, int]]:
    return [(task["capability"], task["stage"]) for task in view["tasks"]]


def _step_names(view: dict[str, Any]) -> list[str]:
    return [step["name"] for step in view["run"]["steps"]]


class StubPlanner:
    """Planner for tests: raises the queued errors first, then plans like `RuleBasedPlanner`
    (optionally as if the customer had confirmed substitutes)."""

    name = "stub"
    step_kind: StepKind = "deterministic"

    def __init__(
        self, *, errors: list[Exception] | None = None, ignore_consent: bool = False
    ) -> None:
        self._errors = list(errors or [])
        self._ignore_consent = ignore_consent
        self.calls = 0

    def plan(self, facts: PlanFacts) -> PlanningResult:
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        if self._ignore_consent:
            facts = facts.model_copy(update={"substitute_consent": "confirmed"})
        return RuleBasedPlanner().plan(facts)


def _transient() -> PlannerFailed:
    return PlannerFailed("Provider timed out", transient=True)


def _stored(engine: Engine, inquiry: Inquiry) -> InquiryOrchestration | None:
    with Session(engine) as session:
        return session.exec(
            select(InquiryOrchestration).where(col(InquiryOrchestration.inquiry_id) == inquiry.id)
        ).first()


# --- Seed scenarios ---------------------------------------------------------------------


def test_acme_runs_four_tasks_in_two_stages(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    body = _analyze(auth_client, acme)

    view = body["orchestration"]
    assert view["status"] == "completed"
    assert (view["consent"], view["planner"], view["error"]) == ("confirmed", "fake", None)
    assert view["stale"] is False
    assert view["planner_steps"] == ["plan"]
    assert len(view["planner_choice"]["tasks"]) == 4
    assert _stages(view) == FULL_PLAN_STAGES
    tasks = _tasks(view)
    assert {t["status"] for t in tasks.values()} == {"completed"}
    assert tasks["substitute-compatibility"]["agent"] == "catalog-agent"
    assert tasks["substitute-availability"]["depends_on"] == ["substitute-compatibility"]
    compatibility = tasks["substitute-compatibility"]["result"]["candidates"]
    assert [(c["code"], c["compatibility"]) for c in compatibility] == [("ABC-110", "full")]
    availability = tasks["substitute-availability"]["result"]["candidates"]
    assert [(c["code"], c["stock"], c["covers_shortage"]) for c in availability] == [
        ("ABC-110", 40, True)
    ]
    offers = tasks["supplier-availability"]["result"]["offers"]
    assert [
        (o["quantity"], o["available_on"], o["meets_deadline"], o["covers_shortage"])
        for o in offers
    ] == [(200, "2026-11-09", False, True)]
    history = tasks["customer-history"]["result"]
    assert (history["orders_count"], history["signal"]) == (2, "accepted_before")
    # Its own run, besides the analysis and the checks.
    assert view["run"]["id"] not in (body["run"]["id"], body["checks"]["run"]["id"])


def test_omega_skips_substitutes(
    auth_client: TestClient, use_extractor: ExtractorSetter, omega: Inquiry
) -> None:
    view = _analyze(auth_client, omega)["orchestration"]

    assert (view["status"], view["consent"]) == ("completed", "refused")
    assert _stages(view) == [("supplier-availability", 1), ("customer-history", 1)]
    tasks = _tasks(view)
    offers = tasks["supplier-availability"]["result"]["offers"]
    assert [
        (o["quantity"], o["available_on"], o["meets_deadline"], o["covers_shortage"])
        for o in offers
    ] == [(80, "2026-11-10", True, True)]
    assert tasks["customer-history"]["result"]["signal"] == "declined_before"
    assert not any(name.startswith("agent:substitute") for name in _step_names(view))


def test_delta_has_unconfirmed_consent_and_no_full_cover(
    auth_client: TestClient, use_extractor: ExtractorSetter, delta: Inquiry
) -> None:
    view = _analyze(auth_client, delta)["orchestration"]

    assert (view["status"], view["consent"]) == ("completed", "unconfirmed")
    assert _stages(view) == FULL_PLAN_STAGES
    tasks = _tasks(view)
    availability = tasks["substitute-availability"]["result"]["candidates"]
    assert [(c["code"], c["covers_shortage"]) for c in availability] == [("ABC-110", False)]
    offers = tasks["supplier-availability"]["result"]["offers"]
    assert [(o["quantity"], o["meets_deadline"], o["covers_shortage"]) for o in offers] == [
        (200, None, False)
    ]
    assert tasks["customer-history"]["result"]["signal"] == "no_substitute_history"


def test_standard_inquiry_is_not_orchestrated(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    biuro_max: Inquiry,
    migrated_engine: Engine,
) -> None:
    body = _analyze(auth_client, biuro_max)

    assert body["checks"]["outcome"] == "standard"
    assert body["orchestration"] is None
    assert _stored(migrated_engine, biuro_max) is None


def test_orchestration_run_traces_every_step(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    view = _analyze(auth_client, acme)["orchestration"]

    trace = view["run"]
    assert (trace["subject_type"], trace["subject_id"]) == ("inquiry", str(acme.id))
    assert trace["status"] == "completed"
    names = _step_names(view)
    assert names[:3] == ["plan", "validate-plan", "match-capabilities"]
    assert sorted(names[3:]) == sorted(f"agent:{c}" for c, _ in FULL_PLAN_STAGES)
    assert names[-1] == "agent:substitute-availability"  # stage 2 starts after stage 1
    assert {step["kind"] for step in trace["steps"]} == {"deterministic"}
    assert {step["status"] for step in trace["steps"]} == {"ok"}
    for task in view["tasks"]:
        assert task["steps"] == [f"agent:{task['capability']}"]
    totals = trace["totals"]
    assert (totals["input_tokens"], totals["output_tokens"]) == (0, 0)
    assert totals["duration_ms"] <= totals["steps_duration_ms"] + WALL_TIME_TOLERANCE_MS


# --- Failures ---------------------------------------------------------------------------


def test_transient_planner_error_is_retried(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    planner = StubPlanner(errors=[_transient()])

    run_orchestration(migrated_engine, acme.id, planner, planner_retry_delay_s=0)

    view = _orchestration(auth_client, acme)
    assert view is not None
    assert view["status"] == "completed"
    assert (view["planner"], view["planner_steps"]) == ("stub", ["plan", "plan#2"])
    steps = view["run"]["steps"]
    assert [(s["name"], s["status"], s["error_type"]) for s in steps[:3]] == [
        ("plan", "failed", "PlannerFailed"),
        ("plan#2", "ok", None),
        ("validate-plan", "ok", None),
    ]
    assert view["run"]["status"] == "completed"


def test_planner_failing_twice_is_failed(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    planner = StubPlanner(errors=[_transient(), _transient()])

    run_orchestration(migrated_engine, acme.id, planner, planner_retry_delay_s=0)

    view = _orchestration(auth_client, acme)
    assert view is not None
    assert view["status"] == "failed"
    assert view["error"] == {
        "kind": "planner_failed",
        "code": "unavailable",
        "message": "Provider timed out",
    }
    assert (view["planner_choice"], view["tasks"]) == (None, [])
    assert _step_names(view) == ["plan", "plan#2"]
    assert planner.calls == 2
    assert "PlannerFailed" in caplog.text


def test_permanent_planner_error_is_not_retried(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    planner = StubPlanner(errors=[PlannerFailed("Bad response", transient=False)])

    run_orchestration(migrated_engine, acme.id, planner, planner_retry_delay_s=0)

    view = _orchestration(auth_client, acme)
    assert view is not None
    assert (view["status"], view["error"]["code"]) == ("failed", "failed")
    assert view["planner_steps"] == ["plan"]


def test_plan_breaking_consent_is_rejected_and_kept(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    omega: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert omega.id is not None
    _analyze(auth_client, omega)

    run_orchestration(migrated_engine, omega.id, StubPlanner(ignore_consent=True))

    view = _orchestration(auth_client, omega)
    assert view is not None
    assert view["status"] == "failed"
    assert (view["error"]["kind"], view["error"]["code"]) == ("plan_rejected", "substitute_refused")
    assert len(view["planner_choice"]["tasks"]) == 4  # the rejected choice is shown
    assert view["tasks"] == []
    # Rejection is a result, not a failure of the step.
    assert [(s["name"], s["status"]) for s in view["run"]["steps"]] == [
        ("plan", "ok"),
        ("validate-plan", "ok"),
    ]


def test_incomplete_registry_is_a_capability_mismatch(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    without_catalog = [a for a in AGENTS if a.name != "catalog-agent"]

    run_orchestration(migrated_engine, acme.id, RuleBasedPlanner(), agents=without_catalog)

    view = _orchestration(auth_client, acme)
    assert view is not None
    assert view["status"] == "failed"
    assert view["error"] == {
        "kind": "capability_mismatch",
        "code": "no_agent",
        "message": "Capability substitute-compatibility has no agent",
    }
    assert [(s["name"], s["status"]) for s in view["run"]["steps"]] == [
        ("plan", "ok"),
        ("validate-plan", "ok"),
        ("match-capabilities", "ok"),
    ]


def test_agent_failing_after_retry_is_partial(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)

    def unavailable(engine: Engine, agent_input: AgentInput) -> AgentResult:
        raise OperationalError("SELECT 1", {}, Exception("connection lost"))

    agents = [
        AgentSpec(name=a.name, capabilities=a.capabilities, run=unavailable)
        if a.name == "catalog-agent"
        else a
        for a in AGENTS
    ]

    run_orchestration(
        migrated_engine, acme.id, RuleBasedPlanner(), agents=agents, agent_retry_delay_s=0
    )

    view = _orchestration(auth_client, acme)
    assert view is not None
    assert (view["status"], view["error"]) == ("partial", None)
    tasks = _tasks(view)
    failed = tasks["substitute-compatibility"]
    assert (failed["status"], failed["error_type"]) == ("failed", "OperationalError")
    assert failed["steps"] == ["agent:substitute-compatibility", "agent:substitute-compatibility#2"]
    assert (
        tasks["substitute-availability"]["status"],
        tasks["substitute-availability"]["steps"],
    ) == (
        "skipped",
        [],
    )
    assert tasks["supplier-availability"]["status"] == "completed"
    assert tasks["customer-history"]["status"] == "completed"
    assert "agent:substitute-availability" not in _step_names(view)


# --- Versions -------------------------------------------------------------------------


def test_refusing_substitutes_changes_the_plan(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    analysis = _analyze(auth_client, acme)

    corrected = _correct(auth_client, analysis, substitute_allowed=False)

    view = corrected["orchestration"]
    assert (view["consent"], view["status"], view["stale"]) == ("refused", "completed", False)
    assert _stages(view) == [("supplier-availability", 1), ("customer-history", 1)]
    assert view["run"]["id"] != analysis["orchestration"]["run"]["id"]


def test_correction_removing_the_exception_deletes_the_orchestration(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    analysis = _analyze(auth_client, acme)
    assert analysis["orchestration"] is not None

    corrected = _correct(auth_client, analysis, quantity=40)

    assert corrected["checks"]["outcome"] == "standard"
    assert corrected["orchestration"] is None
    assert _stored(migrated_engine, acme) is None


def test_recheck_orchestrates_again(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    analysis = _analyze(auth_client, acme)

    response = auth_client.post(_checks_path(acme.id))

    assert response.status_code == 200
    view = response.json()["orchestration"]
    assert view["status"] == "completed"
    assert view["run"]["id"] != analysis["orchestration"]["run"]["id"]


def test_result_of_a_replaced_analysis_version_is_dropped(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    stored = _analyze(auth_client, acme)["orchestration"]

    class CorrectingPlanner(StubPlanner):
        def plan(self, facts: PlanFacts) -> PlanningResult:
            # A correction saved while the orchestration runs: the analysis version changes.
            with Session(migrated_engine) as session:
                session.execute(
                    update(InquiryAnalysis)
                    .where(col(InquiryAnalysis.inquiry_id) == acme.id)
                    .values(corrected_at=datetime.now(UTC))
                )
                session.commit()
            return super().plan(facts)

    run_orchestration(migrated_engine, acme.id, CorrectingPlanner())

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.run_id == stored["run"]["id"]  # the earlier result was kept
    assert row.result["planner"] == "fake"
    with Session(migrated_engine) as session:
        latest = session.exec(
            select(TraceRun)
            .where(
                col(TraceRun.subject_type) == "inquiry",
                col(TraceRun.subject_id) == str(acme.id),
            )
            .order_by(col(TraceRun.id).desc())
        ).first()
    assert latest is not None
    assert latest.id != stored["run"]["id"]  # the dropped run was still traced
    assert latest.status == "completed"


def test_stale_is_computed_on_read(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    view = _analyze(auth_client, acme)["orchestration"]
    assert view["stale"] is False
    with Session(migrated_engine) as session:
        session.execute(
            update(InquiryAnalysis)
            .where(col(InquiryAnalysis.inquiry_id) == acme.id)
            .values(corrected_at=datetime.now(UTC))
        )
        session.commit()

    reread = _orchestration(auth_client, acme)

    assert reread is not None
    assert reread["stale"] is True
    assert reread["run"]["id"] == view["run"]["id"]


def test_stored_result_not_matching_schema_is_hidden(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _analyze(auth_client, acme)
    with Session(migrated_engine) as session:
        session.execute(
            update(InquiryOrchestration)
            .where(col(InquiryOrchestration.inquiry_id) == acme.id)
            .values(result={"removed_field": "x"})
        )
        session.commit()

    response = auth_client.get(_analysis_path(acme.id))

    assert response.status_code == 200
    assert response.json()["orchestration"] is None
    assert "ValidationError" in caplog.text
    assert "removed_field" not in caplog.text
