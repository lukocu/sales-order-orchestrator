from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update
from sqlmodel import Session, col

from app.checks.models import InquiryChecks
from tests.conftest import TEST_EMAIL_DOMAIN, ExtractorSetter, InquiryFactory
from tests.test_parsing_extractors import ACME, BIURO_MAX


@pytest.mark.parametrize("path", ["/api/inquiries", "/api/inquiries/1"])
def test_without_session_is_401(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_list_is_newest_first(auth_client: TestClient, make_inquiry: InquiryFactory) -> None:
    now = datetime.now(UTC)
    oldest = make_inquiry(received_at=now - timedelta(hours=2), subject="oldest")
    newest = make_inquiry(received_at=now, subject="newest")
    middle = make_inquiry(received_at=now - timedelta(hours=1), subject="middle")

    response = auth_client.get("/api/inquiries")

    assert response.status_code == 200
    rows = [r for r in response.json() if r["sender_email"].endswith(f"@{TEST_EMAIL_DOMAIN}")]
    assert [r["id"] for r in rows] == [newest.id, middle.id, oldest.id]
    assert set(rows[0]) == {
        "id",
        "sender_name",
        "sender_email",
        "subject",
        "received_at",
        "outcome",
    }


def test_same_time_is_ordered_by_id_desc(
    auth_client: TestClient, make_inquiry: InquiryFactory
) -> None:
    received_at = datetime.now(UTC)
    first = make_inquiry(received_at=received_at)
    second = make_inquiry(received_at=received_at)

    rows = [
        r
        for r in auth_client.get("/api/inquiries").json()
        if r["sender_email"].endswith(f"@{TEST_EMAIL_DOMAIN}")
    ]

    assert [r["id"] for r in rows] == [second.id, first.id]


def test_detail_includes_body(auth_client: TestClient, make_inquiry: InquiryFactory) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC), subject="With body")

    response = auth_client.get(f"/api/inquiries/{inquiry.id}")

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["subject"], body["body"]) == (
        inquiry.id,
        "With body",
        "Test inquiry body.",
    )
    assert body["sender_email"] == inquiry.sender_email


def test_unknown_inquiry_is_json_404(auth_client: TestClient) -> None:
    response = auth_client.get("/api/inquiries/2147483647")

    assert response.status_code == 404
    assert response.json() == {"detail": "Inquiry not found"}


@pytest.mark.parametrize("inquiry_id", [0, 2_147_483_648])
def test_out_of_range_inquiry_id_is_422(auth_client: TestClient, inquiry_id: int) -> None:
    response = auth_client.get(f"/api/inquiries/{inquiry_id}")

    assert response.status_code == 422


@pytest.mark.parametrize("path", ["/api/inquiries", "/api/inquiries/1"])
def test_unreachable_database_is_json_503(client_without_db: TestClient, path: str) -> None:
    # Any cookie: without one the 401 comes before the database is touched.
    client_without_db.cookies.set("session", "any-token")

    response = client_without_db.get(path)

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_list_and_detail_show_only_a_current_outcome(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    make_inquiry: InquiryFactory,
    migrated_engine: Engine,
) -> None:
    now = datetime.now(UTC)
    checked = make_inquiry(received_at=now, subject=BIURO_MAX[0], body=BIURO_MAX[1])
    unchecked = make_inquiry(received_at=now, subject=ACME[0], body=ACME[1])
    stale = make_inquiry(received_at=now, subject=ACME[0], body=ACME[1])
    assert auth_client.post(f"/api/inquiries/{checked.id}/analysis").status_code == 200
    assert auth_client.post(f"/api/inquiries/{stale.id}/analysis").status_code == 200
    with Session(migrated_engine) as session:
        # A result computed from an older version of the analysis.
        session.execute(
            update(InquiryChecks)
            .where(col(InquiryChecks.inquiry_id) == stale.id)
            .values(analysis_version=now - timedelta(days=1))
        )
        session.commit()

    rows = {r["id"]: r for r in auth_client.get("/api/inquiries").json()}

    assert rows[checked.id]["outcome"] == "standard"
    assert rows[unchecked.id]["outcome"] is None
    assert rows[stale.id]["outcome"] is None
    for inquiry, outcome in ((checked, "standard"), (unchecked, None), (stale, None)):
        detail = auth_client.get(f"/api/inquiries/{inquiry.id}").json()
        assert detail["outcome"] == outcome
