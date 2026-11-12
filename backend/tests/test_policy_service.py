"""Policy stage in the inquiry chain: evaluate, store, read and re-run, in fake mode."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update
from sqlmodel import Session, col, select

from app.inquiries.models import Inquiry
from app.orchestration.planning import PlannerFailed
from app.policy import service as policy_service
from app.policy.models import InquiryPolicyVerdict, PolicyRule
from app.policy.service import NothingToEvaluate, policy_after_recommendation
from app.recommendation.models import InquiryRecommendation
from tests.conftest import ExtractorSetter, InquiryFactory, PlannerSetter, RecommenderSetter
from tests.test_orchestration_service import StubPlanner
from tests.test_parsing_extractors import ACME, BIURO_MAX, DELTA, OMEGA
from tests.test_recommendation_service import StubRecommender


def _analysis_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/analysis"


def _path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/policy"


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


def _policy(client: TestClient, inquiry: Inquiry) -> dict[str, Any] | None:
    view: dict[str, Any] | None = client.get(_analysis_path(inquiry.id)).json()["policy"]
    return view


def _stored(engine: Engine, inquiry: Inquiry) -> InquiryPolicyVerdict | None:
    with Session(engine) as session:
        return session.exec(
            select(InquiryPolicyVerdict).where(col(InquiryPolicyVerdict.inquiry_id) == inquiry.id)
        ).first()


def _verdicts(view: dict[str, Any]) -> dict[str, str]:
    return {rule["code"]: rule["verdict"] for rule in view["rules"]}


def _amounts(rule: dict[str, Any]) -> tuple[Decimal, Decimal]:
    """A rule's actual value and threshold (JSON strings) as numbers."""
    return Decimal(rule["actual"]), Decimal(rule["threshold"])


def _set_threshold(engine: Engine, code: str, threshold: Decimal) -> None:
    with Session(engine) as session:
        session.execute(
            update(PolicyRule).where(col(PolicyRule.code) == code).values(threshold=threshold)
        )
        session.commit()


@pytest.fixture
def restore_thresholds(migrated_engine: Engine) -> Iterator[None]:
    """`policy_rules` is shared and never cleaned: put the thresholds back after the test."""
    with Session(migrated_engine) as session:
        saved = {rule.code: rule.threshold for rule in session.exec(select(PolicyRule)).all()}
    yield
    for code, threshold in saved.items():
        _set_threshold(migrated_engine, code, threshold)


# --- Seed scenarios ---------------------------------------------------------------------


def test_acme_needs_no_approval(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    body = _analyze(auth_client, acme)

    view = body["policy"]
    assert view is not None
    assert (view["option_id"], view["outcome"], view["stale"]) == (
        "stock+ABC-110",
        "no_approval_needed",
        False,
    )
    assert view["thresholds_are_examples"] is True
    assert [rule["code"] for rule in view["rules"]] == [
        "margin",
        "discount",
        "order_value",
        "credit",
    ]
    assert set(_verdicts(view).values()) == {"pass"}
    margin, _, order_value, _ = view["rules"]
    assert _amounts(margin) == (Decimal("25.51"), Decimal("20"))
    assert _amounts(order_value) == (Decimal("9262.50"), Decimal("30000"))
    # Its own run with one deterministic step, after the recommendation's.
    assert view["run"]["id"] != body["recommendation"]["run"]["id"]
    assert [(s["name"], s["kind"], s["status"]) for s in view["run"]["steps"]] == [
        ("rules", "deterministic", "ok")
    ]
    totals = view["run"]["totals"]
    assert (totals["input_tokens"], totals["output_tokens"]) == (0, 0)
    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.outcome == "no_approval_needed"
    with Session(migrated_engine) as session:
        recommendation = session.exec(
            select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == acme.id)
        ).one()
    assert (row.recommendation_id, row.recommended_at) == (
        recommendation.id,
        recommendation.recommended_at,
    )


def test_omega_needs_no_approval(
    auth_client: TestClient, use_extractor: ExtractorSetter, make_inquiry: InquiryFactory
) -> None:
    view = _analyze(auth_client, _inquiry(make_inquiry, OMEGA))["policy"]

    assert view["outcome"] == "no_approval_needed"
    assert set(_verdicts(view).values()) == {"pass"}


def test_delta_requires_a_supervisor(
    auth_client: TestClient, use_extractor: ExtractorSetter, delta: Inquiry
) -> None:
    view = _analyze(auth_client, delta)["policy"]

    assert view["outcome"] == "requires_supervisor"
    discount = view["rules"][1]
    assert (discount["code"], discount["verdict"]) == ("discount", "fail")
    assert _amounts(discount) == (Decimal("25"), Decimal("15"))
    # Credit is evaluated with the selected option's value, not the full requested quantity.
    assert _verdicts(view)["credit"] == "pass"


def test_standard_inquiry_has_no_policy(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    biuro_max: Inquiry,
    migrated_engine: Engine,
) -> None:
    body = _analyze(auth_client, biuro_max)

    assert body["checks"]["outcome"] == "standard"
    assert body["policy"] is None
    assert _stored(migrated_engine, biuro_max) is None


def test_thresholds_are_read_from_policy_rules(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    delta: Inquiry,
    migrated_engine: Engine,
    restore_thresholds: None,
) -> None:
    _analyze(auth_client, delta)
    _set_threshold(migrated_engine, "discount_max_percent", Decimal("30.00"))

    response = auth_client.post(_path(delta.id))

    assert response.status_code == 200
    discount = response.json()["policy"]["rules"][1]
    assert (discount["verdict"], Decimal(discount["threshold"])) == ("pass", Decimal("30"))


# --- Chain and pins ---------------------------------------------------------------------


def test_rerun_recommendation_reevaluates_the_policy(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    before = _analyze(auth_client, acme)

    response = auth_client.post(f"/api/inquiries/{acme.id}/recommendation")

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["recommended_at"] != before["recommendation"]["recommended_at"]
    view = body["policy"]
    assert (view["outcome"], view["stale"]) == ("no_approval_needed", False)
    assert view["run"]["id"] != before["policy"]["run"]["id"]
    assert view["evaluated_at"] != before["policy"]["evaluated_at"]
    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.recommended_at == datetime.fromisoformat(body["recommendation"]["recommended_at"])


def test_failed_recommendation_removes_the_verdict(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_recommender: RecommenderSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert _analyze(auth_client, acme)["policy"] is not None
    use_recommender(StubRecommender(option_id="no-such-option"))

    response = auth_client.post(f"/api/inquiries/{acme.id}/recommendation")

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["status"] == "failed"
    assert body["policy"] is None
    assert _stored(migrated_engine, acme) is None


def test_failed_recommendation_after_orchestration_gives_no_verdict(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_recommender: RecommenderSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    use_recommender(StubRecommender(option_id="no-such-option"))

    body = _analyze(auth_client, acme)

    assert body["recommendation"]["status"] == "failed"
    assert body["policy"] is None
    assert _stored(migrated_engine, acme) is None


def test_verdict_of_another_recommendation_is_stale(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert _analyze(auth_client, acme)["policy"]["stale"] is False
    with Session(migrated_engine) as session:
        session.execute(
            update(InquiryPolicyVerdict)
            .where(col(InquiryPolicyVerdict.inquiry_id) == acme.id)
            .values(recommended_at=datetime(2020, 1, 1, tzinfo=UTC))
        )
        session.commit()

    view = _policy(auth_client, acme)

    assert view is not None
    assert view["stale"] is True


def test_outdated_recommendation_makes_the_verdict_stale_and_rerun_409(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    _analyze(auth_client, acme)
    with Session(migrated_engine) as session:
        # The recommendation was computed from another check result.
        session.execute(
            update(InquiryRecommendation)
            .where(col(InquiryRecommendation.inquiry_id) == acme.id)
            .values(checks_checked_at=datetime(2020, 1, 1, tzinfo=UTC))
        )
        session.commit()

    body = auth_client.get(_analysis_path(acme.id)).json()
    assert body["recommendation"]["stale"] is True
    assert body["policy"]["stale"] is True

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "Nothing to evaluate"}
    assert _stored(migrated_engine, acme) is None  # the verdict of old data is dropped


def test_outdated_call_does_not_delete_a_current_verdict(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert acme.id is not None
    stored = _analyze(auth_client, acme)["policy"]

    def nothing(session: Session, inquiry_id: int) -> None:
        # A call that read its inputs while the recommendation was being replaced.
        raise NothingToEvaluate

    monkeypatch.setattr(policy_service, "_read_inputs", nothing)

    policy_after_recommendation(migrated_engine, acme.id)

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.run_id == stored["run"]["id"]  # pinned to the current recommendation: kept


def test_removing_the_exception_cascades_to_the_verdict(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    analysis = _analyze(auth_client, acme)
    assert analysis["policy"] is not None

    # The re-check after the correction finds no exception and deletes the recommendation.
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
    assert (corrected["recommendation"], corrected["policy"]) == (None, None)
    assert _stored(migrated_engine, acme) is None


def test_unexpected_error_after_recommendation_keeps_the_analysis(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret inquiry content")

    monkeypatch.setattr(policy_service, "evaluate", fail)

    body = _analyze(auth_client, acme)

    assert body["recommendation"]["status"] == "completed"
    assert body["policy"] is None
    assert "RuntimeError" in caplog.text
    assert "secret inquiry content" not in caplog.text


def test_stored_verdict_not_matching_schema_is_hidden(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _analyze(auth_client, acme)
    with Session(migrated_engine) as session:
        session.execute(
            update(InquiryPolicyVerdict)
            .where(col(InquiryPolicyVerdict.inquiry_id) == acme.id)
            .values(result={"removed_field": "x"})
        )
        session.commit()

    response = auth_client.get(_analysis_path(acme.id))

    assert response.status_code == 200
    assert response.json()["policy"] is None
    assert "ValidationError" in caplog.text
    assert "removed_field" not in caplog.text


# --- API --------------------------------------------------------------------------------


def test_rerun_returns_a_new_policy_run(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    analysis = _analyze(auth_client, acme)

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["run"]["id"] == analysis["recommendation"]["run"]["id"]
    view = body["policy"]
    assert (view["outcome"], view["stale"]) == ("no_approval_needed", False)
    assert view["run"]["id"] != analysis["policy"]["run"]["id"]
    assert auth_client.get(_analysis_path(acme.id)).json() == body


def test_without_recommendation_is_409(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_planner: PlannerSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    use_planner(StubPlanner(errors=[PlannerFailed("Bad response", transient=False)]))
    assert _analyze(auth_client, acme)["recommendation"] is None

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "Nothing to evaluate"}
    assert _stored(migrated_engine, acme) is None


def test_standard_inquiry_is_409(
    auth_client: TestClient, use_extractor: ExtractorSetter, biuro_max: Inquiry
) -> None:
    _analyze(auth_client, biuro_max)

    response = auth_client.post(_path(biuro_max.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "Nothing to evaluate"}


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
    stored = _analyze(auth_client, acme)["policy"]

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret inquiry content")

    monkeypatch.setattr(policy_service, "evaluate", fail)
    caplog.clear()

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 500
    assert response.json() == {"detail": "Policy evaluation failed"}
    assert "RuntimeError" in caplog.text
    assert str(acme.id) in caplog.text
    assert "secret inquiry content" not in caplog.text
    monkeypatch.undo()
    kept = _policy(auth_client, acme)
    assert kept is not None
    assert kept["run"]["id"] == stored["run"]["id"]


def test_without_session_is_401(client: TestClient) -> None:
    response = client.post(_path(1))

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
