"""Pending-state and decision races across the complete inquiry processing chain."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from importlib import import_module
from threading import Event
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, update
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.checks import service as checks_service
from app.checks.models import InquiryChecks
from app.checks.rules import classify
from app.draft.drafter import FakeDrafter
from app.draft.models import InquiryDraft, InquiryDraftDecision
from app.draft.service import supervisor_decide
from app.inquiries.models import Inquiry
from app.inquiries.mutations import AwaitingSupervisor, InquiryChanged
from app.orchestration.models import InquiryOrchestration
from app.orchestration.planning import RuleBasedPlanner
from app.orchestration.service import orchestrate_after_checks
from app.parsing.extractor import ExtractionResult
from app.parsing.fake import RuleBasedExtractor
from app.parsing.models import InquiryAnalysis
from app.parsing.service import analyze_inquiry
from app.policy.models import InquiryPolicyVerdict
from app.recommendation.models import InquiryRecommendation
from app.recommendation.recommender import FakeRecommender
from tests.conftest import TEST_PASSWORD, InquiryFactory, UserFactory
from tests.test_draft_api import _edit_body, _login, _supervisor_path
from tests.test_draft_service import _analyze, _inquiry, _read, _submit
from tests.test_parsing_extractors import DELTA

pytestmark = pytest.mark.usefixtures("use_extractor")


@dataclass
class Scenario:
    inquiry: Inquiry
    analysis: dict[str, Any]

    @property
    def id(self) -> int:
        assert self.inquiry.id is not None
        return self.inquiry.id


@pytest.fixture
def scenario(auth_client: TestClient, make_inquiry: InquiryFactory) -> Scenario:
    inquiry = _inquiry(make_inquiry, DELTA)
    return Scenario(inquiry, _analyze(auth_client, inquiry))


@pytest.fixture
def supervisor(make_user: UserFactory) -> User:
    return make_user(role="supervisor", password=TEST_PASSWORD)


def _business_state(engine: Engine, inquiry_id: int) -> list[list[dict[str, Any]]]:
    with Session(engine) as session:
        return [
            [
                row.model_dump(mode="json")
                for row in session.exec(
                    select(model).where(col(model.inquiry_id) == inquiry_id).order_by(col(model.id))
                ).all()
            ]
            for model in (
                InquiryAnalysis,
                InquiryChecks,
                InquiryOrchestration,
                InquiryRecommendation,
                InquiryPolicyVerdict,
                InquiryDraft,
                InquiryDraftDecision,
            )
        ]


MUTATIONS = [
    ("POST", "analysis"),
    ("PUT", "analysis"),
    ("POST", "checks"),
    ("POST", "orchestration"),
    ("POST", "recommendation"),
    ("POST", "policy"),
    ("POST", "draft"),
    ("PUT", "draft"),
    ("POST", "draft/decision"),
    ("POST", "draft/decision:reject"),
]


@pytest.mark.parametrize("as_supervisor", [False, True], ids=["sales", "supervisor"])
@pytest.mark.parametrize(("method", "endpoint"), MUTATIONS)
def test_pending_inquiry_blocks_all_mutations_before_providers(
    auth_client: TestClient,
    migrated_engine: Engine,
    scenario: Scenario,
    test_user: User,
    supervisor: User,
    monkeypatch: pytest.MonkeyPatch,
    as_supervisor: bool,
    method: str,
    endpoint: str,
) -> None:
    _submit(migrated_engine, scenario.inquiry, scenario.analysis["draft"], test_user)
    if as_supervisor:
        _login(auth_client, supervisor)
    before = _business_state(migrated_engine, scenario.id)
    current = _read(auth_client, scenario.inquiry)

    def forbidden(*args: object, **kwargs: object) -> Any:
        pytest.fail("A pending mutation reached a provider or check")

    monkeypatch.setattr(RuleBasedExtractor, "extract", forbidden)
    monkeypatch.setattr(RuleBasedPlanner, "plan", forbidden)
    monkeypatch.setattr(FakeRecommender, "choose", forbidden)
    monkeypatch.setattr(FakeDrafter, "write", forbidden)
    monkeypatch.setattr(checks_service, "classify", forbidden)
    payload: dict[str, Any] = {}
    if method == "PUT" and endpoint == "analysis":
        payload = {
            "fields": current["fields"],
            "reviewed": [],
            "analyzed_at": current["analyzed_at"],
        }
    elif method == "PUT":
        payload = _edit_body(current["draft"])
    elif endpoint.startswith("draft/decision"):
        payload = {
            "updated_at": current["draft"]["updated_at"],
            "action": "reject" if endpoint.endswith(":reject") else "approve",
            "reason": "Change pending offer",
        }
    path = endpoint.removesuffix(":reject")
    response = auth_client.request(method, f"/api/inquiries/{scenario.id}/{path}", json=payload)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Inquiry awaiting supervisor decision",
        "code": "AWAITING_SUPERVISOR",
    }
    assert _business_state(migrated_engine, scenario.id) == before


@pytest.mark.parametrize("corrupt", [False, True], ids=["stale", "unreadable"])
def test_raw_pending_state_blocks_analysis_even_without_a_usable_draft(
    auth_client: TestClient,
    migrated_engine: Engine,
    scenario: Scenario,
    test_user: User,
    corrupt: bool,
) -> None:
    _submit(migrated_engine, scenario.inquiry, scenario.analysis["draft"], test_user)
    with Session(migrated_engine) as session:
        if corrupt:
            session.execute(
                update(InquiryDraft)
                .where(col(InquiryDraft.inquiry_id) == scenario.id)
                .values(result={"invalid": True})
            )
        else:
            session.execute(
                update(InquiryRecommendation)
                .where(col(InquiryRecommendation.inquiry_id) == scenario.id)
                .values(status="failed")
            )
        session.commit()
    before = _business_state(migrated_engine, scenario.id)
    response = auth_client.post(f"/api/inquiries/{scenario.id}/analysis")
    assert response.status_code == 409
    assert _business_state(migrated_engine, scenario.id) == before


@pytest.mark.parametrize("outcome", ["pending", "approve", "reject"])
@pytest.mark.parametrize("stage", ["checks", "orchestration", "recommendation", "policy", "draft"])
def test_stage_cannot_store_after_submission_or_subsequent_decision(
    auth_client: TestClient,
    migrated_engine: Engine,
    scenario: Scenario,
    test_user: User,
    supervisor: User,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    outcome: str,
) -> None:
    expected: list[list[dict[str, Any]]] = []

    def decide_meanwhile() -> None:
        nonlocal expected
        _submit(migrated_engine, scenario.inquiry, scenario.analysis["draft"], test_user)
        if outcome != "pending":
            token = _read(auth_client, scenario.inquiry)["draft"]["updated_at"]

            supervisor_decide(
                migrated_engine,
                scenario.id,
                AuthUser.from_user(supervisor),
                updated_at=datetime.fromisoformat(token),
                action="approve" if outcome == "approve" else "reject",
                reason="Review",
            )
        expected = _business_state(migrated_engine, scenario.id)

    if stage == "checks":

        def classified(*args: Any, **kwargs: Any) -> Any:
            result = classify(*args, **kwargs)
            decide_meanwhile()
            return result

        monkeypatch.setattr(checks_service, "classify", classified)
    else:
        module = import_module(f"app.{stage}.service")
        original_store: Callable[..., None] = module._store

        def store(*args: Any, **kwargs: Any) -> None:
            decide_meanwhile()
            original_store(*args, **kwargs)

        monkeypatch.setattr(module, "_store", store)

    def no_followup(*args: object, **kwargs: object) -> None:
        pytest.fail("A conflict continued into a downstream stage")

    # Parsing retries used to run these unconditionally in `finally`.
    if stage == "recommendation":
        monkeypatch.setattr("app.parsing.service.policy_after_recommendation", no_followup)
    if stage in ("recommendation", "policy"):
        monkeypatch.setattr("app.parsing.service.draft_after_policy", no_followup)
    response = auth_client.post(f"/api/inquiries/{scenario.id}/{stage}")

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Inquiry awaiting supervisor decision"
            if outcome == "pending"
            else "Inquiry changed, reload"
        ),
        "code": "AWAITING_SUPERVISOR" if outcome == "pending" else "INQUIRY_CHANGED",
    }
    assert expected
    assert _business_state(migrated_engine, scenario.id) == expected


@pytest.mark.parametrize("outcome", ["pending", "approve", "reject"])
@pytest.mark.parametrize("stage", ["orchestration", "recommendation", "policy", "draft"])
def test_cleanup_cannot_delete_a_submission_created_after_stage_entry(
    auth_client: TestClient,
    migrated_engine: Engine,
    scenario: Scenario,
    test_user: User,
    supervisor: User,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    outcome: str,
) -> None:
    module = import_module(f"app.{stage}.service")
    expected: list[list[dict[str, Any]]] = []
    cleanup = module._drop_unless_exception if stage == "orchestration" else module._drop_outdated

    def cleanup_after_submission(*args: Any, **kwargs: Any) -> Any:
        nonlocal expected
        _submit(migrated_engine, scenario.inquiry, scenario.analysis["draft"], test_user)
        if outcome != "pending":
            token = _read(auth_client, scenario.inquiry)["draft"]["updated_at"]
            supervisor_decide(
                migrated_engine,
                scenario.id,
                AuthUser.from_user(supervisor),
                updated_at=datetime.fromisoformat(token),
                action="approve" if outcome == "approve" else "reject",
                reason="Review",
            )
        # Force the normal cleanup predicate true, using a simulated external stale result.
        with Session(migrated_engine) as session:
            if stage == "orchestration":
                session.execute(
                    update(InquiryChecks)
                    .where(col(InquiryChecks.inquiry_id) == scenario.id)
                    .values(outcome="standard", exception_type=None)
                )
            else:
                session.execute(
                    update(InquiryRecommendation)
                    .where(col(InquiryRecommendation.inquiry_id) == scenario.id)
                    .values(status="failed")
                )
            session.commit()
        expected = _business_state(migrated_engine, scenario.id)
        return cleanup(*args, **kwargs)

    if stage == "orchestration":
        monkeypatch.setattr(module, "_drop_unless_exception", cleanup_after_submission)
    else:
        monkeypatch.setattr(module, "_drop_outdated", cleanup_after_submission)

        def missing(*args: object, **kwargs: object) -> None:
            if stage == "recommendation":
                raise module.NothingToRecommend
            if stage == "policy":
                raise module.NothingToEvaluate
            raise module.NothingToDraft

        monkeypatch.setattr(module, "_read_inputs", missing)

    def operation() -> None:
        if stage == "orchestration":
            orchestrate_after_checks(
                migrated_engine, scenario.id, RuleBasedPlanner(), FakeRecommender(), FakeDrafter()
            )
        elif stage == "recommendation":
            module.recommend_after_orchestration(
                migrated_engine, scenario.id, FakeRecommender(), FakeDrafter()
            )
        elif stage == "policy":
            module.policy_after_recommendation(migrated_engine, scenario.id)
        else:
            module.draft_after_policy(migrated_engine, scenario.id, FakeDrafter())

    with pytest.raises(AwaitingSupervisor if outcome == "pending" else InquiryChanged):
        operation()
    assert expected
    assert _business_state(migrated_engine, scenario.id) == expected


@pytest.mark.parametrize("outcome", ["pending", "approve", "reject"])
def test_parallel_first_analysis_cannot_overwrite_a_submitted_result(
    auth_client: TestClient,
    migrated_engine: Engine,
    make_inquiry: InquiryFactory,
    test_user: User,
    supervisor: User,
    outcome: str,
) -> None:
    inquiry = _inquiry(make_inquiry, DELTA)
    assert inquiry.id is not None
    inquiry_id = inquiry.id
    extracting, resume = Event(), Event()

    class PausedExtractor(RuleBasedExtractor):
        def extract(self, subject: str, body: str, reference_date: date) -> ExtractionResult:
            extracting.set()
            assert resume.wait(15), "Test did not release the extractor"
            return super().extract(subject, body, reference_date)

    with ThreadPoolExecutor(max_workers=1) as pool:
        older = pool.submit(
            analyze_inquiry,
            migrated_engine,
            PausedExtractor(),
            inquiry_id,
            AuthUser.from_user(test_user),
            RuleBasedPlanner(),
            FakeRecommender(),
            FakeDrafter(),
        )
        try:
            assert extracting.wait(10), "Older request never reached extraction"
            # No lock/connection spans extraction: a second first analysis can finish.
            current = _analyze(auth_client, inquiry)
            _submit(migrated_engine, inquiry, current["draft"], test_user)
            if outcome != "pending":
                token = _read(auth_client, inquiry)["draft"]["updated_at"]
                supervisor_decide(
                    migrated_engine,
                    inquiry_id,
                    AuthUser.from_user(supervisor),
                    updated_at=datetime.fromisoformat(token),
                    action="approve" if outcome == "approve" else "reject",
                    reason="Review",
                )
            expected = _business_state(migrated_engine, inquiry_id)
        finally:
            resume.set()
        with pytest.raises(AwaitingSupervisor if outcome == "pending" else InquiryChanged):
            older.result(timeout=15)
    assert _business_state(migrated_engine, inquiry_id) == expected


@pytest.mark.parametrize(
    "damage", ["stale", "unreadable", "missing_policy", "missing_history", "edited_checks"]
)
def test_rejection_recovers_pending_data_and_can_be_followed_by_new_analysis(
    auth_client: TestClient,
    migrated_engine: Engine,
    scenario: Scenario,
    test_user: User,
    supervisor: User,
    damage: str,
) -> None:
    if damage == "edited_checks":
        edited = auth_client.put(
            f"/api/inquiries/{scenario.id}/draft", json=_edit_body(scenario.analysis["draft"])
        )
        assert edited.status_code == 200
        scenario.analysis = edited.json()
    _submit(migrated_engine, scenario.inquiry, scenario.analysis["draft"], test_user)
    pending = _read(auth_client, scenario.inquiry)
    with Session(migrated_engine) as session:
        if damage in ("unreadable", "missing_history"):
            session.execute(
                update(InquiryDraft)
                .where(col(InquiryDraft.inquiry_id) == scenario.id)
                .values(result={"unreadable": True})
            )
        elif damage == "stale":
            session.execute(
                update(InquiryRecommendation)
                .where(col(InquiryRecommendation.inquiry_id) == scenario.id)
                .values(status="failed")
            )
        elif damage == "edited_checks":
            session.execute(
                update(InquiryChecks)
                .where(col(InquiryChecks.inquiry_id) == scenario.id)
                .values(results={"unreadable": True})
            )
        else:
            session.execute(
                delete(InquiryPolicyVerdict).where(
                    col(InquiryPolicyVerdict.inquiry_id) == scenario.id
                )
            )
        if damage == "missing_history":
            session.execute(
                delete(InquiryDraftDecision).where(
                    col(InquiryDraftDecision.inquiry_id) == scenario.id
                )
            )
        session.commit()
    _login(auth_client, supervisor)
    payload = {
        "updated_at": pending["draft"]["updated_at"],
        "action": "reject",
        "reason": "Popraw dane",
    }
    response = auth_client.post(_supervisor_path(scenario.id), json=payload)
    assert response.status_code == 200
    decision = response.json()["decisions"][-1]
    assert decision["action"] == "supervisor_reject"
    assert decision["reason"] == "Popraw dane"
    assert decision["snapshot"] == (
        None if damage == "missing_history" else pending["decisions"][-1]["snapshot"]
    )
    with Session(migrated_engine) as session:
        row = session.exec(
            select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == scenario.id)
        ).one()
        assert row.status == "rejected"
    duplicate = auth_client.post(_supervisor_path(scenario.id), json=payload)
    assert duplicate.status_code == 409
    reread = auth_client.get(f"/api/inquiries/{scenario.id}/analysis")
    assert reread.status_code == 200
    assert len(reread.json()["decisions"]) == len(response.json()["decisions"])
    _login(auth_client, test_user)
    after = auth_client.post(f"/api/inquiries/{scenario.id}/analysis")
    assert after.status_code == 200
    assert after.json()["draft"]["status"] == "draft"
