"""HTTP contracts independent of English business text and private exception data."""

import logging

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.api import analysis, auth, mailbox
from app.api.errors import ApiHTTPException, database_unavailable
from app.draft.offer import InvalidEdit
from app.draft.service import (
    DraftChanged,
    DraftNotEditable,
    DraftStale,
    NotAwaitingSupervisor,
    NothingToDraft,
    OwnSubmission,
    PolicyMissing,
    ReasonRequired,
)
from app.inquiries.mutations import AwaitingSupervisor, InquiryChanged
from app.mailbox.client import MailboxAuthFailed, MailboxNotConfigured, MailboxUnavailable
from app.main import create_app
from app.parsing.extractor import ExtractionFailed, ExtractionNotConfigured, ExtractionRateLimited


@pytest.mark.parametrize(
    ("error", "code", "status", "detail"),
    [
        (DraftChanged(), "DRAFT_CHANGED", 409, "Draft changed, reload"),
        (DraftNotEditable(), "DRAFT_NOT_EDITABLE", 409, "Draft cannot be changed"),
        (DraftStale(), "DRAFT_STALE", 409, "Draft is stale"),
        (PolicyMissing(), "POLICY_MISSING", 409, "Policy verdict missing"),
        (NothingToDraft(), "NOTHING_TO_DRAFT", 409, "Nothing to draft"),
        (
            NotAwaitingSupervisor(),
            "NOT_AWAITING_SUPERVISOR",
            409,
            "Draft is not awaiting supervisor",
        ),
        (OwnSubmission(), "OWN_SUBMISSION", 409, "Cannot approve your own submission"),
        (ReasonRequired(), "REASON_REQUIRED", 422, "Reason is required"),
        (
            InvalidEdit("Quantity must be at least 1"),
            "INVALID_EDIT",
            422,
            "Quantity must be at least 1",
        ),
    ],
)
def test_decision_codes_at_source(error: Exception, code: str, status: int, detail: str) -> None:
    mapped = analysis._decision_error(error)
    assert isinstance(mapped, ApiHTTPException)
    assert (mapped.code, mapped.status_code, mapped.detail) == (code, status, detail)


@pytest.mark.parametrize(
    ("error", "code"),
    [(AwaitingSupervisor(), "AWAITING_SUPERVISOR"), (InquiryChanged(), "INQUIRY_CHANGED")],
)
def test_mutation_codes_are_chosen_by_type(
    error: AwaitingSupervisor | InquiryChanged, code: str
) -> None:
    error.args = ("Different explanatory text",)
    mapped = analysis._mutation_conflict(error)
    assert mapped.code == code
    assert mapped.detail == "Different explanatory text"
    assert mapped.status_code == 409


@pytest.mark.parametrize(
    ("error", "code", "status"),
    [
        (ExtractionNotConfigured("private key"), "ANALYSIS_NOT_CONFIGURED", 503),
        (ExtractionRateLimited("private response"), "ANALYSIS_RATE_LIMITED", 503),
        (ExtractionFailed("private response"), "ANALYSIS_FAILED", 502),
    ],
)
def test_extraction_errors_have_safe_codes(
    error: ExtractionFailed | ExtractionNotConfigured | ExtractionRateLimited,
    code: str,
    status: int,
) -> None:
    mapped = analysis._extraction_error(error)
    assert isinstance(mapped, ApiHTTPException)
    assert (mapped.code, mapped.status_code) == (code, status)
    assert "private" not in str(mapped.detail)


@pytest.mark.parametrize(
    ("error", "code", "status"),
    [
        (MailboxNotConfigured("private"), "MAILBOX_NOT_CONFIGURED", 503),
        (MailboxAuthFailed("private"), "MAILBOX_AUTH_FAILED", 502),
        (MailboxUnavailable("private"), "MAILBOX_UNAVAILABLE", 502),
    ],
)
def test_mailbox_errors_have_safe_codes(
    error: MailboxNotConfigured | MailboxAuthFailed | MailboxUnavailable, code: str, status: int
) -> None:
    mapped = mailbox._mailbox_failed(error)
    assert isinstance(mapped, ApiHTTPException)
    assert (mapped.code, mapped.status_code) == (code, status)
    assert "private" not in str(mapped.detail)


def test_common_response_preserves_detail_headers_and_has_no_private_params() -> None:
    app = create_app()

    @app.get("/test-error")
    def endpoint() -> None:
        raise ApiHTTPException(
            status_code=429,
            detail="Original detail",
            code="RATE_LIMITED",
            headers={"Retry-After": "30", "WWW-Authenticate": "Session"},
        )

    with TestClient(app) as client:
        response = client.get("/test-error")
    assert response.status_code == 429
    assert response.json() == {"detail": "Original detail", "code": "RATE_LIMITED"}
    assert response.headers["retry-after"] == "30"
    assert response.headers["www-authenticate"] == "Session"


class ValidatedRequest(BaseModel):
    count: int = Field(ge=1)


def test_validation_keeps_legacy_detail_and_does_not_copy_input_into_params() -> None:
    app = create_app()

    @app.post("/test-validation")
    def endpoint(body: ValidatedRequest) -> ValidatedRequest:
        return body

    with TestClient(app) as client:
        response = client.post("/test-validation", json={"count": "private-input"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["detail"][0]["loc"] == ["body", "count"]
    assert body["detail"][0]["type"] == "int_parsing"
    assert set(body) == {"detail", "code"}


def test_unknown_exception_has_generic_response_and_original_logged_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app()
    failure = RuntimeError("original diagnostic")

    @app.get("/test-unexpected")
    def endpoint() -> None:
        raise failure

    with caplog.at_level(logging.ERROR), TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-unexpected")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error", "code": "INTERNAL_ERROR"}
    record = next(r for r in caplog.records if r.message == "Unhandled API error")
    assert record.exc_info is not None
    assert record.exc_info[1] is failure


@pytest.mark.parametrize("method", ["get", "post"])
def test_unknown_api_route_has_code(method: str) -> None:
    with TestClient(create_app()) as client:
        response = client.request(method, "/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found", "code": "NOT_FOUND"}


def test_legacy_http_error_preserves_headers() -> None:
    app = create_app()

    @app.get("/test-legacy")
    def endpoint() -> None:
        raise HTTPException(403, "Existing detail", headers={"X-Error": "yes"})

    with TestClient(app) as client:
        response = client.get("/test-legacy")
    assert response.json() == {"detail": "Existing detail", "code": "FORBIDDEN"}
    assert response.headers["x-error"] == "yes"


def test_auth_error_codes_are_distinct() -> None:
    assert auth._invalid_credentials().detail == "Invalid username or password"
    invalid = auth._invalid_credentials()
    assert isinstance(invalid, ApiHTTPException)
    assert invalid.code == "INVALID_CREDENTIALS"
    assert database_unavailable().code == "DATABASE_UNAVAILABLE"
