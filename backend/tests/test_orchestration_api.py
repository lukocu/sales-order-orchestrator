from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.inquiries.models import Inquiry
from app.orchestration import service as orchestration_service
from tests.conftest import ExtractorSetter, InquiryFactory
from tests.test_parsing_extractors import ACME, BIURO_MAX


def _analysis_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/analysis"


def _path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/orchestration"


def _inquiry(make_inquiry: InquiryFactory, seed: tuple[str, str, object]) -> Inquiry:
    subject, body, _ = seed
    return make_inquiry(
        received_at=datetime(2026, 11, 2, 9, 0, tzinfo=UTC), subject=subject, body=body
    )


@pytest.fixture
def acme(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, ACME)


@pytest.fixture
def biuro_max(make_inquiry: InquiryFactory) -> Inquiry:
    return _inquiry(make_inquiry, BIURO_MAX)


def test_rerun_returns_a_new_orchestration_run(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    analysis = auth_client.post(_analysis_path(acme.id)).json()

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["run"]["id"] == analysis["checks"]["run"]["id"]
    view = body["orchestration"]
    assert (view["status"], view["stale"]) == ("completed", False)
    assert view["run"]["id"] != analysis["orchestration"]["run"]["id"]
    assert auth_client.get(_analysis_path(acme.id)).json() == body


def test_standard_inquiry_is_409(
    auth_client: TestClient, use_extractor: ExtractorSetter, biuro_max: Inquiry
) -> None:
    assert auth_client.post(_analysis_path(biuro_max.id)).status_code == 200

    response = auth_client.post(_path(biuro_max.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "Nothing to orchestrate"}


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
    stored = auth_client.post(_analysis_path(acme.id)).json()["orchestration"]

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret inquiry content")

    monkeypatch.setattr(orchestration_service, "execute", fail)
    caplog.clear()

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 500
    assert response.json() == {"detail": "Orchestration failed"}
    assert "RuntimeError" in caplog.text
    assert str(acme.id) in caplog.text
    assert "secret inquiry content" not in caplog.text
    monkeypatch.undo()
    kept = auth_client.get(_analysis_path(acme.id)).json()["orchestration"]
    assert kept["run"]["id"] == stored["run"]["id"]


def test_without_session_is_401(client: TestClient) -> None:
    response = client.post(_path(1))

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_unreachable_database_is_json_503(client_without_db: TestClient) -> None:
    client_without_db.cookies.set("session", "any-token")

    response = client_without_db.post(_path(1))

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
