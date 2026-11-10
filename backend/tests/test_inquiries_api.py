from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_EMAIL_DOMAIN, InquiryFactory


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
    assert set(rows[0]) == {"id", "sender_name", "sender_email", "subject", "received_at"}


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
