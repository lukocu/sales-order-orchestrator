from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update
from sqlmodel import Session, col, select

from app.inquiries.models import Inquiry
from app.parsing.extractor import (
    ExtractionError,
    ExtractionFailed,
    ExtractionNotConfigured,
    ExtractionRateLimited,
    ExtractionResult,
)
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import ModelExtraction
from app.tracing.models import TraceRun
from app.tracing.pricing import LlmUsage
from app.tracing.summary import get_run_summary
from tests.conftest import ExtractorSetter, InquiryFactory, StubExtractor

# Seed inquiry ACME (migrations/versions/0003_users_inquiries.py); Monday 2026-11-02.
ACME_SENDER = "Marek Nowak (ACME Sp. z o.o.)"
ACME_SUBJECT = "Zapytanie ofertowe: 80 szt. ABC-100"
ACME_BODY = (
    "Dzień dobry,\n\n"
    "prosimy o ofertę na 80 szt. ABC-100 z dostawą do piątku. "
    "Jeśli nie mają Państwo pełnej ilości, możemy przyjąć podobny model "
    "o zbliżonych parametrach.\n\n"
    "Prosimy o najlepszą cenę i informację o terminie dostawy.\n\n"
    "Pozdrawiam,\n"
    "Marek Nowak\n"
    "Dział zakupów, ACME Sp. z o.o."
)
ACME_RECEIVED_AT = datetime(2026, 11, 2, 8, 15, tzinfo=UTC)
ACME_FIELDS = {
    "customer": "ACME Sp. z o.o.",
    "product_code": "ABC-100",
    "quantity": 80,
    "deadline": "2026-11-06",
    "deadline_text": "do piątku",
    "substitute_allowed": True,
    "price_kind": "best_price",
    "price_value": None,
    "price_text": "najlepszą cenę",
}

GROQ_USAGE = LlmUsage(
    provider="groq",
    model="openai/gpt-oss-120b",
    input_tokens=1500,
    output_tokens=300,
    raw={"prompt_tokens": 1500, "completion_tokens": 300},
)


def _extraction(**overrides: Any) -> ModelExtraction:
    values: dict[str, Any] = {
        "customer": "ACME Sp. z o.o.",
        "product_code": "ABC-100",
        "quantity": 80,
        "deadline_text": "do piątku",
        "deadline_date": "2026-11-06",
        "substitute_allowed": True,
        "price_kind": "best_price",
        "price_value": None,
        "price_text": "najlepszą cenę",
        "uncertain": [],
    }
    values.update(overrides)
    return ModelExtraction.model_validate(values)


def _path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/analysis"


@pytest.fixture
def acme(make_inquiry: InquiryFactory) -> Inquiry:
    return make_inquiry(
        received_at=ACME_RECEIVED_AT,
        subject=ACME_SUBJECT,
        body=ACME_BODY,
        sender_name=ACME_SENDER,
    )


def _correction(analysis: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """PUT body sending the analysis back as read, with `changes` applied."""
    body: dict[str, Any] = {
        "fields": analysis["fields"],
        "reviewed": [],
        "analyzed_at": analysis["analyzed_at"],
    }
    body.update(changes)
    return body


@pytest.mark.parametrize("method", ["GET", "POST", "PUT"])
def test_without_session_is_401(client: TestClient, method: str) -> None:
    response = client.request(method, _path(1))

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.parametrize("method", ["GET", "POST", "PUT"])
def test_unreachable_database_is_json_503(client_without_db: TestClient, method: str) -> None:
    # Any cookie: without one the 401 comes before the database is touched.
    client_without_db.cookies.set("session", "any-token")
    body = {
        "fields": ACME_FIELDS,
        "reviewed": [],
        "analyzed_at": "2026-11-10T10:00:00+00:00",
    }

    response = client_without_db.request(method, _path(1), json=body if method == "PUT" else None)

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_get_before_analysis_is_null(auth_client: TestClient, acme: Inquiry) -> None:
    response = auth_client.get(_path(acme.id))

    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_unknown_inquiry_is_404(
    auth_client: TestClient, use_extractor: ExtractorSetter, method: str
) -> None:
    response = auth_client.request(method, _path(2_147_483_647))

    assert response.status_code == 404
    assert response.json() == {"detail": "Inquiry not found"}


@pytest.mark.parametrize("inquiry_id", [0, 2_147_483_648])
def test_out_of_range_inquiry_id_is_422(auth_client: TestClient, inquiry_id: int) -> None:
    assert auth_client.get(_path(inquiry_id)).status_code == 422


def test_rule_based_analysis_of_acme(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    response = auth_client.post(_path(acme.id))

    assert response.status_code == 200
    body = response.json()
    assert body["inquiry_id"] == acme.id
    assert body["extractor"] == "fake"
    assert body["reference_date"] == "2026-11-02"
    assert body["fields"] == ACME_FIELDS
    assert body["model_fields"] == ACME_FIELDS
    assert body["uncertain"] == {}
    assert body["corrected_fields"] == []
    assert body["analyzed_by_name"] == "Test User"
    assert body["corrected_at"] is None
    assert body["corrected_by_name"] is None
    run = body["run"]
    assert (run["subject_type"], run["subject_id"]) == ("inquiry", str(acme.id))
    assert run["status"] == "completed"
    steps = [(s["name"], s["kind"], s["price_status"]) for s in run["steps"]]
    assert steps == [
        ("parse", "deterministic", "not_applicable"),
        ("resolve-deadline", "deterministic", "not_applicable"),
    ]
    assert auth_client.get(_path(acme.id)).json() == body


def test_reference_date_is_the_day_in_warsaw(
    auth_client: TestClient, use_extractor: ExtractorSetter, make_inquiry: InquiryFactory
) -> None:
    # 23:30 UTC on Sunday is already Monday 00:30 in Warsaw.
    inquiry = make_inquiry(
        received_at=datetime(2026, 11, 1, 23, 30, tzinfo=UTC), subject=ACME_SUBJECT, body=ACME_BODY
    )

    body = auth_client.post(_path(inquiry.id)).json()

    assert body["reference_date"] == "2026-11-02"
    assert body["fields"]["deadline"] == "2026-11-06"


def test_llm_analysis_is_priced(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    use_extractor(
        StubExtractor(
            name="groq",
            step_kind="llm",
            result=ExtractionResult(extraction=_extraction(), usage=GROQ_USAGE),
        )
    )

    body = auth_client.post(_path(acme.id)).json()

    assert body["extractor"] == "groq"
    parse = body["run"]["steps"][0]
    assert (parse["name"], parse["kind"], parse["price_status"]) == ("parse", "llm", "priced")
    assert (parse["provider"], parse["model"]) == ("groq", "openai/gpt-oss-120b")
    assert (parse["input_tokens"], parse["output_tokens"]) == (1500, 300)
    assert Decimal(parse["cost_usd"]) > 0
    assert Decimal(body["run"]["totals"]["cost_usd"]) == Decimal(parse["cost_usd"])
    assert [step["name"] for step in body["run"]["steps"]] == ["parse", "resolve-deadline"]
    checks_run = body["checks"]["run"]
    assert checks_run["id"] != body["run"]["id"]
    assert "llm" not in {step["kind"] for step in checks_run["steps"]}
    assert (checks_run["totals"]["input_tokens"], checks_run["totals"]["output_tokens"]) == (0, 0)
    assert Decimal(checks_run["totals"]["cost_usd"]) == 0


def test_uncertain_fields_are_returned(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    use_extractor(
        StubExtractor(
            result=ExtractionResult(
                extraction=_extraction(quantity=None, substitute_allowed=None), usage=None
            )
        )
    )

    body = auth_client.post(_path(acme.id)).json()

    assert body["uncertain"] == {"quantity": "Missing", "substitute_allowed": "Not stated"}


def test_correction_marks_field_and_clears_flags(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    use_extractor(
        StubExtractor(
            result=ExtractionResult(
                extraction=_extraction(quantity=None, substitute_allowed=None, customer=None),
                usage=None,
            )
        )
    )
    analysis = auth_client.post(_path(acme.id)).json()

    response = auth_client.put(
        _path(acme.id),
        json=_correction(
            analysis,
            fields={**analysis["fields"], "quantity": 80},
            reviewed=["substitute_allowed"],
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["quantity"] == 80
    assert body["fields"]["substitute_allowed"] is None
    assert body["model_fields"]["quantity"] is None
    assert body["corrected_fields"] == ["quantity"]
    assert body["uncertain"] == {"customer": "Missing"}
    assert body["corrected_by_name"] == "Test User"
    assert body["corrected_at"] is not None
    assert body["analyzed_at"] == analysis["analyzed_at"]
    assert auth_client.get(_path(acme.id)).json() == body


def test_reanalysis_replaces_result_and_drops_corrections(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    first = auth_client.post(_path(acme.id)).json()
    corrected = auth_client.put(
        _path(acme.id), json=_correction(first, fields={**first["fields"], "quantity": 90})
    ).json()
    assert corrected["corrected_fields"] == ["quantity"]

    second = auth_client.post(_path(acme.id)).json()

    assert second["fields"] == second["model_fields"] == ACME_FIELDS
    assert second["corrected_fields"] == []
    assert (second["corrected_at"], second["corrected_by_name"]) == (None, None)
    assert second["analyzed_at"] != first["analyzed_at"]
    assert second["run"]["id"] != first["run"]["id"]


def test_stale_correction_is_409_and_changes_nothing(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    stale = auth_client.post(_path(acme.id)).json()
    current = auth_client.post(_path(acme.id)).json()

    response = auth_client.put(
        _path(acme.id), json=_correction(stale, fields={**stale["fields"], "quantity": 90})
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Analysis changed, reload"}
    assert auth_client.get(_path(acme.id)).json() == current


def test_correction_without_analysis_is_404(auth_client: TestClient, acme: Inquiry) -> None:
    response = auth_client.put(
        _path(acme.id),
        json={"fields": ACME_FIELDS, "reviewed": [], "analyzed_at": "2026-11-10T10:00:00Z"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No analysis yet"}


@pytest.mark.parametrize(
    "changes",
    [
        {"fields": {**ACME_FIELDS, "price_kind": "discount_percent", "price_value": "150"}},
        {"fields": {**ACME_FIELDS, "quantity": 0}},
        {"reviewed": ["unknown"]},
        {"analyzed_at": "2026-11-10T10:00:00"},  # without a time zone
    ],
)
def test_invalid_correction_is_422(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    changes: dict[str, Any],
) -> None:
    analysis = auth_client.post(_path(acme.id)).json()

    response = auth_client.put(_path(acme.id), json=_correction(analysis, **changes))

    assert response.status_code == 422
    assert auth_client.get(_path(acme.id)).json() == analysis


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (ExtractionNotConfigured("no key"), 503, "LLM not configured"),
        (ExtractionRateLimited("429"), 503, "LLM rate limit reached, try again later"),
        (ExtractionFailed("bad json"), 502, "Analysis failed, try again"),
    ],
)
def test_extraction_error_keeps_existing_result(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    error: ExtractionError,
    status_code: int,
    detail: str,
) -> None:
    before = auth_client.post(_path(acme.id)).json()
    use_extractor(StubExtractor(name="groq", step_kind="llm", error=error))

    response = auth_client.post(_path(acme.id))

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    assert auth_client.get(_path(acme.id)).json() == before


def test_failed_extraction_still_records_usage(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    use_extractor(
        StubExtractor(
            name="groq",
            step_kind="llm",
            error=ExtractionFailed("content does not match the schema", usage=GROQ_USAGE),
        )
    )

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 502
    with Session(migrated_engine) as session:
        run_id = session.exec(
            select(TraceRun.id)
            .where(
                col(TraceRun.subject_type) == "inquiry",
                col(TraceRun.subject_id) == str(acme.id),
            )
            .order_by(col(TraceRun.id).desc())
        ).first()
        assert run_id is not None
        summary = get_run_summary(session, run_id)
    assert summary is not None
    assert summary.status == "failed"
    [parse] = summary.steps
    assert (parse.name, parse.status, parse.error_type) == ("parse", "failed", "ExtractionFailed")
    assert parse.price_status == "priced"
    assert parse.cost_usd is not None and parse.cost_usd > 0


def test_stored_analysis_not_matching_schema_is_500(
    auth_client: TestClient, acme: Inquiry, migrated_engine: Engine
) -> None:
    assert auth_client.post(_path(acme.id)).status_code == 200
    with Session(migrated_engine) as session:
        session.execute(
            update(InquiryAnalysis)
            .where(col(InquiryAnalysis.inquiry_id) == acme.id)
            .values(fields={"removed_field": "x"})
        )
        session.commit()

    response = auth_client.get(_path(acme.id))

    assert response.status_code == 500
    assert response.json() == {"detail": "Stored analysis is invalid"}
