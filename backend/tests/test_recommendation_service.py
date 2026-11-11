"""Recommendation stage in the inquiry chain: run, store, read and re-run, in fake mode."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update
from sqlmodel import Session, col, select

from app.inquiries.models import Inquiry
from app.orchestration.models import InquiryOrchestration
from app.orchestration.planning import PlannerFailed
from app.parsing.models import InquiryAnalysis
from app.recommendation import service as recommendation_service
from app.recommendation.models import InquiryRecommendation
from app.recommendation.recommender import (
    FakeRecommender,
    RecommenderFailed,
    RecommenderOutput,
)
from app.recommendation.schema import (
    RecommendationFacts,
    RecommendationOption,
    RecommenderChoice,
)
from app.recommendation.service import (
    NothingToRecommend,
    recommend_after_orchestration,
    run_recommendation,
)
from app.tracing.models import StepKind
from app.tracing.pricing import LlmUsage
from tests.conftest import ExtractorSetter, InquiryFactory, PlannerSetter, RecommenderSetter
from tests.test_orchestration_service import StubPlanner
from tests.test_parsing_extractors import ACME, BIURO_MAX, DELTA, OMEGA

USAGE = LlmUsage(provider="groq", model="openai/gpt-oss-120b", input_tokens=900, output_tokens=60)


def _analysis_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/analysis"


def _path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/recommendation"


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
def biuro_max(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, BIURO_MAX)


def _analyze(client: TestClient, inquiry: Inquiry) -> dict[str, Any]:
    response = client.post(_analysis_path(inquiry.id))
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def _recommendation(client: TestClient, inquiry: Inquiry) -> dict[str, Any] | None:
    view: dict[str, Any] | None = client.get(_analysis_path(inquiry.id)).json()["recommendation"]
    return view


def _stored(engine: Engine, inquiry: Inquiry) -> InquiryRecommendation | None:
    with Session(engine) as session:
        return session.exec(
            select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry.id)
        ).first()


def _chosen(view: dict[str, Any]) -> dict[str, Any]:
    option_id = view["choice"]["option_id"]
    chosen: dict[str, Any] = next(o for o in view["options"] if o["id"] == option_id)
    return chosen


def _steps(view: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(s["name"], s["kind"], s["status"]) for s in view["run"]["steps"]]


class StubRecommender:
    """Recommender for tests: raises the queued errors first, then chooses like
    `FakeRecommender`, optionally with another option id."""

    name = "stub"

    def __init__(
        self,
        *,
        errors: list[Exception] | None = None,
        option_id: str | None = None,
        step_kind: StepKind = "deterministic",
    ) -> None:
        self._errors = list(errors or [])
        self._option_id = option_id
        self.step_kind: StepKind = step_kind
        self.calls = 0

    def choose(
        self, facts: RecommendationFacts, options: Sequence[RecommendationOption]
    ) -> RecommenderOutput:
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        output = FakeRecommender().choose(facts, options)
        if self._option_id is None:
            return output
        choice = RecommenderChoice(
            option_id=self._option_id, justification="Inna opcja.", cited_signals=[]
        )
        return RecommenderOutput(choice=choice, usage=None)


def _transient(usage: LlmUsage | None = None) -> RecommenderFailed:
    return RecommenderFailed("Provider timed out", transient=True, usage=usage)


# --- Seed scenarios ---------------------------------------------------------------------


def test_acme_recommends_stock_and_substitute(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    body = _analyze(auth_client, acme)

    view = body["recommendation"]
    assert view is not None
    assert (view["status"], view["recommender"], view["error"]) == (
        "completed",
        "rule-based",
        None,
    )
    assert (view["stale"], view["choice_steps"]) == (False, ["choose"])
    chosen = _chosen(view)
    assert chosen["id"] == "stock+ABC-110"
    assert (chosen["band"], chosen["covered_quantity"], chosen["margin_percent"]) == (
        "HIGH",
        80,
        "25.51",
    )
    assert set(view["choice"]["cited_signals"]) <= {s["code"] for s in chosen["signals"]}
    assert view["choice"]["justification"]
    assert len(view["options"]) > 1  # every option is shown, not only the chosen one
    # Its own run, after the orchestration's.
    assert view["run"]["id"] not in (
        body["checks"]["run"]["id"],
        body["orchestration"]["run"]["id"],
    )
    assert _steps(view) == [("options", "deterministic", "ok"), ("choose", "deterministic", "ok")]
    totals = view["run"]["totals"]
    assert (totals["input_tokens"], totals["output_tokens"]) == (0, 0)


@pytest.mark.parametrize(
    ("seed", "option_id", "band", "covered", "margin"),
    [
        (OMEGA, "stock+supplier:Hydro-Valve", "HIGH", 120, "23.75"),
        (DELTA, "stock+ABC-110+supplier:Sensortech Polska", "LOW", 290, "14.29"),
    ],
)
def test_other_seed_inquiries(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    make_inquiry: InquiryFactory,
    seed: tuple[str, str, date],
    option_id: str,
    band: str,
    covered: int,
    margin: str,
) -> None:
    view = _analyze(auth_client, _inquiry(make_inquiry, seed))["recommendation"]

    assert view["status"] == "completed"
    chosen = _chosen(view)
    assert chosen["id"] == option_id
    assert (chosen["band"], chosen["covered_quantity"], chosen["margin_percent"]) == (
        band,
        covered,
        margin,
    )


def test_standard_inquiry_has_no_recommendation(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    biuro_max: Inquiry,
    migrated_engine: Engine,
) -> None:
    body = _analyze(auth_client, biuro_max)

    assert body["checks"]["outcome"] == "standard"
    assert body["recommendation"] is None
    assert _stored(migrated_engine, biuro_max) is None


# --- Chain and versions -----------------------------------------------------------------


def test_correction_removing_the_exception_deletes_the_recommendation(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    analysis = _analyze(auth_client, acme)
    assert analysis["recommendation"] is not None

    response = auth_client.put(
        _analysis_path(acme.id),
        json={
            "fields": {**analysis["fields"], "quantity": 40},
            "reviewed": [],
            "analyzed_at": analysis["analyzed_at"],
        },
    )

    assert response.status_code == 200
    corrected = response.json()
    assert corrected["checks"]["outcome"] == "standard"
    assert (corrected["orchestration"], corrected["recommendation"]) == (None, None)
    assert _stored(migrated_engine, acme) is None


def test_outdated_call_does_not_delete_a_current_recommendation(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert acme.id is not None
    stored = _analyze(auth_client, acme)["recommendation"]

    def nothing(session: Session, inquiry_id: int) -> None:
        # A call that read its inputs while the orchestration was being replaced.
        raise NothingToRecommend

    monkeypatch.setattr(recommendation_service, "_read_inputs", nothing)

    recommend_after_orchestration(migrated_engine, acme.id, FakeRecommender())

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.run_id == stored["run"]["id"]  # pinned to the current orchestration: kept


def test_failed_orchestration_removes_the_recommendation(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_planner: PlannerSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert _analyze(auth_client, acme)["recommendation"] is not None
    use_planner(StubPlanner(errors=[PlannerFailed("Bad response", transient=False)]))

    response = auth_client.post(f"/api/inquiries/{acme.id}/orchestration")

    assert response.status_code == 200
    body = response.json()
    assert body["orchestration"]["status"] == "failed"
    assert body["recommendation"] is None
    assert _stored(migrated_engine, acme) is None


def test_failed_orchestration_gives_no_recommendation(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_planner: PlannerSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    use_planner(StubPlanner(errors=[PlannerFailed("Bad response", transient=False)]))

    body = _analyze(auth_client, acme)

    assert body["orchestration"]["status"] == "failed"
    assert body["recommendation"] is None
    assert _stored(migrated_engine, acme) is None
    response = auth_client.post(_path(acme.id))
    assert response.status_code == 409
    assert response.json() == {"detail": "Nothing to recommend"}


def _set_orchestrated_at(engine: Engine, inquiry: Inquiry) -> None:
    with Session(engine) as session:
        session.execute(
            update(InquiryOrchestration)
            .where(col(InquiryOrchestration.inquiry_id) == inquiry.id)
            .values(orchestrated_at=datetime.now(UTC))
        )
        session.commit()


def test_result_of_a_replaced_orchestration_is_dropped_and_stale(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    stored = _analyze(auth_client, acme)["recommendation"]
    assert stored["stale"] is False

    class ReorchestratingRecommender(StubRecommender):
        def choose(
            self, facts: RecommendationFacts, options: Sequence[RecommendationOption]
        ) -> RecommenderOutput:
            # A newer orchestration stored while the recommender chooses.
            _set_orchestrated_at(migrated_engine, acme)
            return super().choose(facts, options)

    run_recommendation(migrated_engine, acme.id, ReorchestratingRecommender())

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.run_id == stored["run"]["id"]  # the earlier result was kept
    reread = _recommendation(auth_client, acme)
    assert reread is not None
    assert reread["stale"] is True  # the newer orchestration has no recommendation yet
    assert reread["recommender"] == "rule-based"


def test_stale_after_an_analysis_correction_is_computed_on_read(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert _analyze(auth_client, acme)["recommendation"]["stale"] is False
    with Session(migrated_engine) as session:
        session.execute(
            update(InquiryAnalysis)
            .where(col(InquiryAnalysis.inquiry_id) == acme.id)
            .values(corrected_at=datetime.now(UTC))
        )
        session.commit()

    reread = _recommendation(auth_client, acme)

    assert reread is not None
    assert reread["stale"] is True


def test_reorchestration_recommends_again(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    stored = _analyze(auth_client, acme)["recommendation"]

    response = auth_client.post(f"/api/inquiries/{acme.id}/orchestration")

    assert response.status_code == 200
    view = response.json()["recommendation"]
    assert (view["status"], view["stale"]) == ("completed", False)
    assert view["run"]["id"] != stored["run"]["id"]


# --- Recommender failures ---------------------------------------------------------------


def test_transient_error_after_orchestration_is_failed_with_options(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_recommender: RecommenderSetter,
    acme: Inquiry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    recommender = StubRecommender(errors=[_transient(USAGE)], step_kind="llm")
    use_recommender(recommender)

    view = _analyze(auth_client, acme)["recommendation"]

    assert recommender.calls == 1  # the automatic path does not retry
    assert view["status"] == "failed"
    assert view["error"] == {
        "kind": "recommender_failed",
        "code": "unavailable",
        "message": "Provider timed out",
    }
    assert (view["choice"], view["choice_steps"]) == (None, ["choose"])
    assert {o["id"] for o in view["options"]} >= {"stock", "stock+ABC-110"}
    assert _steps(view) == [("options", "deterministic", "ok"), ("choose", "llm", "failed")]
    choose = view["run"]["steps"][1]
    assert (choose["error_type"], choose["input_tokens"], choose["output_tokens"]) == (
        "RecommenderFailed",
        900,
        60,
    )
    assert "RecommenderFailed" in caplog.text
    assert str(acme.id) in caplog.text


def test_rerun_retries_a_transient_error(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_recommender: RecommenderSetter,
    acme: Inquiry,
) -> None:
    _analyze(auth_client, acme)
    recommender = StubRecommender(errors=[_transient(), _transient()])
    use_recommender(recommender)

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 200
    view = response.json()["recommendation"]
    assert recommender.calls == 2
    assert (view["status"], view["choice_steps"]) == ("failed", ["choose", "choose#2"])
    assert view["error"]["code"] == "unavailable"
    assert [(s["name"], s["status"]) for s in view["run"]["steps"]] == [
        ("options", "ok"),
        ("choose", "failed"),
        ("choose#2", "failed"),
    ]


def test_rerun_recovers_after_a_transient_error(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    recommender = StubRecommender(errors=[_transient()])

    run_recommendation(migrated_engine, acme.id, recommender, retry_delay_s=0)

    view = _recommendation(auth_client, acme)
    assert view is not None
    assert (view["status"], view["choice_steps"]) == ("completed", ["choose", "choose#2"])
    assert _chosen(view)["id"] == "stock+ABC-110"


def test_unknown_option_is_rejected(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_recommender: RecommenderSetter,
    acme: Inquiry,
) -> None:
    use_recommender(StubRecommender(option_id="no-such-option"))

    view = _analyze(auth_client, acme)["recommendation"]

    assert view["status"] == "failed"
    assert (view["error"]["kind"], view["error"]["code"]) == ("choice_rejected", "unknown_option")
    assert view["choice"] is None  # a rejected choice is never shown as the recommendation
    assert view["options"]
    # Rejection is a result, not a failure of the step.
    assert [(s["name"], s["status"]) for s in view["run"]["steps"]] == [
        ("options", "ok"),
        ("choose", "ok"),
    ]


def test_unexpected_error_after_orchestration_keeps_the_analysis(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret inquiry content")

    monkeypatch.setattr(recommendation_service, "build_options", fail)

    body = _analyze(auth_client, acme)

    assert body["orchestration"]["status"] == "completed"
    assert body["recommendation"] is None
    assert "RuntimeError" in caplog.text
    assert "secret inquiry content" not in caplog.text


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
            update(InquiryRecommendation)
            .where(col(InquiryRecommendation.inquiry_id) == acme.id)
            .values(result={"removed_field": "x"})
        )
        session.commit()

    response = auth_client.get(_analysis_path(acme.id))

    assert response.status_code == 200
    assert response.json()["recommendation"] is None
    assert "ValidationError" in caplog.text
    assert "removed_field" not in caplog.text


# --- API --------------------------------------------------------------------------------


def test_rerun_returns_a_new_recommendation_run(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    analysis = _analyze(auth_client, acme)

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 200
    body = response.json()
    assert body["orchestration"]["run"]["id"] == analysis["orchestration"]["run"]["id"]
    view = body["recommendation"]
    assert (view["status"], view["stale"]) == ("completed", False)
    assert view["run"]["id"] != analysis["recommendation"]["run"]["id"]
    assert auth_client.get(_analysis_path(acme.id)).json() == body


def test_standard_inquiry_is_409(
    auth_client: TestClient, use_extractor: ExtractorSetter, biuro_max: Inquiry
) -> None:
    _analyze(auth_client, biuro_max)

    response = auth_client.post(_path(biuro_max.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "Nothing to recommend"}


def test_without_analysis_is_404(auth_client: TestClient, acme: Inquiry) -> None:
    response = auth_client.post(_path(acme.id))

    assert response.status_code == 404
    assert response.json() == {"detail": "No analysis yet"}


def test_unknown_inquiry_is_404(auth_client: TestClient) -> None:
    response = auth_client.post(_path(2_147_483_647))

    assert response.status_code == 404
    assert response.json() == {"detail": "Inquiry not found"}


def test_unexpected_error_is_json_500(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stored = _analyze(auth_client, acme)["recommendation"]

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret inquiry content")

    monkeypatch.setattr(recommendation_service, "build_options", fail)
    caplog.clear()

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 500
    assert response.json() == {"detail": "Recommendation failed"}
    assert "RuntimeError" in caplog.text
    assert str(acme.id) in caplog.text
    assert "secret inquiry content" not in caplog.text
    monkeypatch.undo()
    kept = _recommendation(auth_client, acme)
    assert kept is not None
    assert kept["run"]["id"] == stored["run"]["id"]


def test_without_session_is_401(client: TestClient) -> None:
    response = client.post(_path(1))

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
