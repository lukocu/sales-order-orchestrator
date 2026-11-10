from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update
from sqlmodel import Session, col, select

from app.checks import service as checks_service
from app.checks.models import InquiryChecks
from app.checks.rules import CustomerRecord, check_credit
from app.checks.schema import CreditCheck, PriceCheck
from app.inquiries.models import Inquiry
from app.parsing.models import InquiryAnalysis
from app.tracing.models import TraceRun
from app.tracing.summary import get_run_summary
from tests.conftest import ExtractorSetter, InquiryFactory
from tests.test_parsing_extractors import ACME, BIURO_MAX

CHECK_STEPS = [
    "match-customer",
    "check-stock",
    "check-price",
    "check-discount",
    "check-credit",
    "classify",
]


def _analysis_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/analysis"


def _checks_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/checks"


def _inquiry(make_inquiry: InquiryFactory, seed: tuple[str, str, Any]) -> Inquiry:
    subject, body, _ = seed
    return make_inquiry(
        received_at=datetime(2026, 11, 3, 9, 0, tzinfo=UTC), subject=subject, body=body
    )


@pytest.fixture
def acme(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, ACME)


@pytest.fixture
def biuro_max(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, BIURO_MAX)


def _correct_quantity(client: TestClient, analysis: dict[str, Any], quantity: int) -> Any:
    response = client.put(
        _analysis_path(analysis["inquiry_id"]),
        json={
            "fields": {**analysis["fields"], "quantity": quantity},
            "reviewed": [],
            "analyzed_at": analysis["analyzed_at"],
        },
    )
    assert response.status_code == 200
    return response.json()


def _assert_deterministic_checks_run(checks_run: dict[str, Any]) -> None:
    assert [step["name"] for step in checks_run["steps"]] == CHECK_STEPS
    assert {step["kind"] for step in checks_run["steps"]} == {"deterministic"}
    assert {step["status"] for step in checks_run["steps"]} == {"ok"}
    totals = checks_run["totals"]
    assert (totals["input_tokens"], totals["output_tokens"]) == (0, 0)
    assert totals["cost_complete"] is True


@pytest.fixture
def broken_checks(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Makes the price check raise until `monkeypatch.undo()`."""

    def fail(*args: object) -> None:
        raise RuntimeError("check failed")

    monkeypatch.setattr(checks_service, "check_price", fail)
    return monkeypatch


def test_standard_inquiry_is_checked_in_own_deterministic_run(
    auth_client: TestClient, use_extractor: ExtractorSetter, biuro_max: Inquiry
) -> None:
    response = auth_client.post(_analysis_path(biuro_max.id))

    assert response.status_code == 200
    body = response.json()
    checks = body["checks"]
    assert checks["outcome"] == "standard"
    assert checks["exception_type"] is None
    assert checks["reasons"] == []
    assert checks["stale"] is False
    assert checks["uncertain_inputs"] == []
    results = checks["results"]
    assert (results["customer"]["status"], results["customer"]["name"]) == (
        "matched",
        "Biuro Max",
    )
    assert results["customer"]["matched_by"] == "name"
    assert (results["stock"]["requested"], results["stock"]["available"]) == (20, 150)
    assert (results["price"]["unit_price"], results["price"]["total"]) == ("85.00", "1700.00")
    assert results["credit"]["status"] == "ok"
    checks_run = checks["run"]
    assert checks_run["id"] != body["run"]["id"]
    assert (checks_run["subject_type"], checks_run["subject_id"]) == ("inquiry", str(biuro_max.id))
    assert checks_run["status"] == "completed"
    _assert_deterministic_checks_run(checks_run)
    assert [step["name"] for step in body["run"]["steps"]] == ["parse", "resolve-deadline"]
    assert auth_client.get(_analysis_path(biuro_max.id)).json() == body


def test_insufficient_stock_is_an_exception(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    checks = auth_client.post(_analysis_path(acme.id)).json()["checks"]

    assert (checks["outcome"], checks["exception_type"]) == ("exception", "insufficient_stock")
    stock = checks["results"]["stock"]
    assert (stock["status"], stock["requested"], stock["available"], stock["shortage"]) == (
        "insufficient",
        80,
        50,
        30,
    )


def test_correction_rechecks_in_a_new_run(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    analysis = auth_client.post(_analysis_path(acme.id)).json()

    corrected = _correct_quantity(auth_client, analysis, 40)

    checks = corrected["checks"]
    assert checks["outcome"] == "standard"
    assert checks["stale"] is False
    assert checks["run"]["id"] not in (analysis["checks"]["run"]["id"], corrected["run"]["id"])
    assert corrected["run"]["id"] == analysis["run"]["id"]
    _assert_deterministic_checks_run(checks["run"])


def test_failed_checks_keep_the_analysis(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    biuro_max: Inquiry,
    broken_checks: pytest.MonkeyPatch,
    migrated_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = auth_client.post(_analysis_path(biuro_max.id))

    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["quantity"] == 20
    assert body["checks"] is None
    assert "RuntimeError" in caplog.text
    assert "check failed" not in caplog.text
    with Session(migrated_engine) as session:
        run_id = session.exec(
            select(TraceRun.id)
            .where(
                col(TraceRun.subject_type) == "inquiry",
                col(TraceRun.subject_id) == str(biuro_max.id),
            )
            .order_by(col(TraceRun.id).desc())
        ).first()
        assert run_id is not None
        summary = get_run_summary(session, run_id)
    assert summary is not None
    assert summary.status == "failed"
    assert [(s.name, s.status) for s in summary.steps] == [
        ("match-customer", "ok"),
        ("check-stock", "ok"),
        ("check-price", "failed"),
    ]
    assert summary.steps[-1].error_type == "RuntimeError"

    broken_checks.undo()
    rechecked = auth_client.post(_checks_path(biuro_max.id))

    assert rechecked.status_code == 200
    assert rechecked.json()["checks"]["outcome"] == "standard"


def test_failed_checks_after_correction_leave_result_stale(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = auth_client.post(_analysis_path(acme.id)).json()
    assert analysis["checks"]["outcome"] == "exception"

    def fail(*args: object) -> None:
        raise RuntimeError("check failed")

    monkeypatch.setattr(checks_service, "check_price", fail)
    corrected = _correct_quantity(auth_client, analysis, 40)

    assert corrected["fields"]["quantity"] == 40
    assert corrected["checks"]["stale"] is True
    assert corrected["checks"]["outcome"] == "exception"
    assert corrected["checks"]["run"]["id"] == analysis["checks"]["run"]["id"]

    monkeypatch.undo()
    response = auth_client.post(_checks_path(acme.id))

    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["quantity"] == 40
    assert (body["checks"]["outcome"], body["checks"]["stale"]) == ("standard", False)
    assert body["checks"]["run"]["id"] != analysis["checks"]["run"]["id"]
    _assert_deterministic_checks_run(body["checks"]["run"])


def test_recheck_returns_a_new_run(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    analysis = auth_client.post(_analysis_path(acme.id)).json()

    response = auth_client.post(_checks_path(acme.id))

    assert response.status_code == 200
    body = response.json()
    assert body["analyzed_at"] == analysis["analyzed_at"]
    assert body["run"]["id"] == analysis["run"]["id"]
    assert body["checks"]["run"]["id"] != analysis["checks"]["run"]["id"]
    assert body["checks"]["outcome"] == "exception"


def test_recheck_with_failing_check_is_json_500(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    broken_checks: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert auth_client.post(_analysis_path(acme.id)).status_code == 200
    caplog.clear()

    response = auth_client.post(_checks_path(acme.id))

    assert response.status_code == 500
    assert response.json() == {"detail": "Checks failed"}
    assert "RuntimeError" in caplog.text
    assert str(acme.id) in caplog.text
    assert "check failed" not in caplog.text


def test_result_of_a_replaced_analysis_version_is_dropped(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert acme.id is not None
    stored = auth_client.post(_analysis_path(acme.id)).json()["checks"]

    def correct_meanwhile(customer: CustomerRecord | None, price: PriceCheck) -> CreditCheck:
        # A correction saved while the checks run: the analysis version changes.
        with Session(migrated_engine) as session:
            session.execute(
                update(InquiryAnalysis)
                .where(col(InquiryAnalysis.inquiry_id) == acme.id)
                .values(corrected_at=datetime.now(UTC))
            )
            session.commit()
        return check_credit(customer, price)

    monkeypatch.setattr(checks_service, "check_credit", correct_meanwhile)

    checks_service.run_checks(migrated_engine, acme.id)

    with Session(migrated_engine) as session:
        row = session.exec(
            select(InquiryChecks).where(col(InquiryChecks.inquiry_id) == acme.id)
        ).one()
        assert row.run_id == stored["run"]["id"]  # the earlier result was kept
        runs = session.exec(
            select(TraceRun)
            .where(
                col(TraceRun.subject_type) == "inquiry",
                col(TraceRun.subject_id) == str(acme.id),
            )
            .order_by(col(TraceRun.id).desc())
        ).all()
    assert runs[0].id != stored["run"]["id"]
    assert runs[0].status == "completed"


def test_recheck_without_analysis_is_404(auth_client: TestClient, acme: Inquiry) -> None:
    response = auth_client.post(_checks_path(acme.id))

    assert response.status_code == 404
    assert response.json() == {"detail": "No analysis yet"}


def test_recheck_of_unknown_inquiry_is_404(auth_client: TestClient) -> None:
    response = auth_client.post(_checks_path(2_147_483_647))

    assert response.status_code == 404
    assert response.json() == {"detail": "Inquiry not found"}


def test_recheck_without_session_is_401(client: TestClient) -> None:
    response = client.post(_checks_path(1))

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_recheck_with_unreachable_database_is_json_503(client_without_db: TestClient) -> None:
    client_without_db.cookies.set("session", "any-token")

    response = client_without_db.post(_checks_path(1))

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_uncertain_inputs_are_listed(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    auth_client.post(_analysis_path(acme.id))
    with Session(migrated_engine) as session:
        session.execute(
            update(InquiryAnalysis)
            .where(col(InquiryAnalysis.inquiry_id) == acme.id)
            .values(uncertain={"quantity": "Unclear", "deadline": "Missing"})
        )
        session.commit()

    checks = auth_client.get(_analysis_path(acme.id)).json()["checks"]

    assert checks["uncertain_inputs"] == ["quantity"]


def test_stored_result_not_matching_schema_can_be_rechecked(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert auth_client.post(_analysis_path(acme.id)).status_code == 200
    with Session(migrated_engine) as session:
        session.execute(
            update(InquiryChecks)
            .where(col(InquiryChecks.inquiry_id) == acme.id)
            .values(results={"removed_field": "x"})
        )
        session.commit()

    response = auth_client.get(_analysis_path(acme.id))

    assert response.status_code == 200
    assert response.json()["checks"] is None
    assert "ValidationError" in caplog.text
    assert "removed_field" not in caplog.text

    rechecked = auth_client.post(_checks_path(acme.id))

    assert rechecked.status_code == 200
    assert rechecked.json()["checks"]["outcome"] == "exception"
    with Session(migrated_engine) as session:
        stored = session.exec(
            select(InquiryChecks.results).where(col(InquiryChecks.inquiry_id) == acme.id)
        ).one()
    assert "removed_field" not in stored
