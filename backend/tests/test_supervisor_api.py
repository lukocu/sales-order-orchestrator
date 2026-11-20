"""Supervisor queue and review read API."""

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlmodel import Session, col, select

from app.auth.models import User
from app.draft.models import InquiryDraft, InquiryDraftDecision
from app.inquiries.models import Inquiry
from app.policy.models import InquiryPolicyVerdict
from tests.conftest import ExtractorSetter, InquiryFactory, UserFactory
from tests.test_parsing_extractors import DELTA


def _path(inquiry_id: int | None) -> str:
    assert inquiry_id is not None
    return f"/api/inquiries/{inquiry_id}"


def _delta(make_inquiry: InquiryFactory) -> Inquiry:
    subject, body, reference = DELTA
    return make_inquiry(
        received_at=datetime(reference.year, reference.month, reference.day, 9, tzinfo=UTC),
        subject=subject,
        body=body,
    )


def _awaiting(client: TestClient, inquiry: Inquiry) -> dict[str, Any]:
    assert inquiry.id is not None
    analyzed = client.post(f"{_path(inquiry.id)}/analysis")
    assert analyzed.status_code == 200
    draft = analyzed.json()["draft"]
    response = client.post(
        f"{_path(inquiry.id)}/draft/decision",
        json={"updated_at": draft["updated_at"], "action": "approve", "reason": "Exception"},
    )
    assert response.status_code == 200
    body = cast(dict[str, Any], response.json())
    return cast(dict[str, Any], body["draft"])


def _login(client: TestClient, user: User) -> None:
    response = client.post(
        "/api/auth/login", json={"username": user.username, "password": "test-password-123"}
    )
    assert response.status_code == 200


@pytest.fixture
def supervisor(make_user: UserFactory) -> User:
    return make_user(role="supervisor", password="test-password-123")


def test_queue_requires_supervisor_and_returns_empty_for_supervisor(
    client: TestClient, auth_client: TestClient, supervisor: User
) -> None:
    assert auth_client.get("/api/supervisor/queue").status_code == 403
    assert auth_client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/supervisor/queue").status_code == 401
    _login(auth_client, supervisor)

    response = auth_client.get("/api/supervisor/queue")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_queue_lists_pending_submission_with_policy_and_count(
    auth_client: TestClient,
    supervisor: User,
    make_inquiry: InquiryFactory,
    use_extractor: ExtractorSetter,
) -> None:
    inquiry = _delta(make_inquiry)
    draft = _awaiting(auth_client, inquiry)
    _login(auth_client, supervisor)

    response = auth_client.get("/api/supervisor/queue")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    (item,) = body["items"]
    assert item["id"] == inquiry.id
    assert item["draft_updated_at"] == draft["updated_at"]
    assert item["submitted_by"] is not None
    assert item["review_state"] == "actionable"
    assert "discount" in {rule["code"] for rule in item["attention_rules"]}
    assert "body" not in item and "sender_email" not in item

    detail = auth_client.get(f"/api/supervisor/reviews/{inquiry.id}")
    assert detail.status_code == 200
    assert detail.json()["offer"]["edited"] is False
    assert detail.json()["policy"]["rules"]
    assert detail.json()["allowed_actions"] == ["reject", "approve"]


def test_queue_orders_ties_by_inquiry_id_and_uses_policy_for_edited_offer(
    migrated_engine: Engine,
    auth_client: TestClient,
    supervisor: User,
    make_inquiry: InquiryFactory,
    use_extractor: ExtractorSetter,
) -> None:
    first = _delta(make_inquiry)
    second = _delta(make_inquiry)
    assert first.id is not None and second.id is not None
    _awaiting(auth_client, first)
    _awaiting(auth_client, second)
    same_time = datetime(2026, 11, 18, 12, tzinfo=UTC)
    with Session(migrated_engine) as session:
        for inquiry in (first, second):
            decision = session.exec(
                select(InquiryDraftDecision).where(
                    col(InquiryDraftDecision.inquiry_id) == inquiry.id,
                    col(InquiryDraftDecision.action) == "approve",
                )
            ).one()
            decision.decided_at = same_time
            session.add(decision)
            draft = session.exec(
                select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry.id)
            ).one()
            result = dict(draft.result)
            offer = dict(result["offer"])
            offer["edited"] = True
            result["offer"] = offer
            draft.result = result
            session.add(draft)
        session.commit()
    _login(auth_client, supervisor)

    response = auth_client.get("/api/supervisor/queue")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == sorted([first.id, second.id])
    assert body["items"][0]["submitted_at"] == same_time.isoformat().replace("+00:00", "Z")
    item = body["items"][0]
    assert item["review_state"] == "actionable"
    detail = auth_client.get(f"/api/supervisor/reviews/{item['id']}").json()
    assert detail["offer"]["edited"] is True
    assert detail["policy"]["rules"]


def test_queue_projects_not_evaluated_attention_rule(
    migrated_engine: Engine,
    auth_client: TestClient,
    supervisor: User,
    make_inquiry: InquiryFactory,
    use_extractor: ExtractorSetter,
) -> None:
    inquiry = _delta(make_inquiry)
    _awaiting(auth_client, inquiry)
    assert inquiry.id is not None
    with Session(migrated_engine) as session:
        verdict = session.exec(
            select(InquiryPolicyVerdict).where(col(InquiryPolicyVerdict.inquiry_id) == inquiry.id)
        ).one()
        policy_result = dict(verdict.result)
        rules = [dict(rule) for rule in policy_result["rules"]]
        discount = next(rule for rule in rules if rule["code"] == "discount")
        discount["verdict"] = "not_evaluated"
        policy_result["rules"] = rules
        verdict.result = policy_result
        session.add(verdict)
        session.commit()
    _login(auth_client, supervisor)

    response = auth_client.get("/api/supervisor/queue")

    assert response.status_code == 200
    item = response.json()["items"][0]
    discount_rule = next(rule for rule in item["attention_rules"] if rule["code"] == "discount")
    assert discount_rule["verdict"] == "not_evaluated"


def test_queue_keeps_stale_submission_visible_without_old_policy(
    migrated_engine: Engine,
    auth_client: TestClient,
    supervisor: User,
    make_inquiry: InquiryFactory,
    use_extractor: ExtractorSetter,
) -> None:
    inquiry = _delta(make_inquiry)
    assert inquiry.id is not None
    _awaiting(auth_client, inquiry)
    with Session(migrated_engine) as session:
        draft = session.exec(
            select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry.id)
        ).one()
        draft.recommended_at = datetime(2000, 1, 1, tzinfo=UTC)
        session.add(draft)
        session.commit()
    _login(auth_client, supervisor)

    item = auth_client.get("/api/supervisor/queue").json()["items"][0]
    detail = auth_client.get(f"/api/supervisor/reviews/{inquiry.id}").json()

    assert item["review_state"] == "stale"
    assert item["attention_rules"] == []
    assert detail["policy"] is None
    assert detail["allowed_actions"] == ["reject"]


def test_queue_keeps_stale_and_unreadable_drafts_and_uses_fallback_timestamp(
    migrated_engine: Engine,
    auth_client: TestClient,
    supervisor: User,
    make_inquiry: InquiryFactory,
    use_extractor: ExtractorSetter,
) -> None:
    inquiry = _delta(make_inquiry)
    assert inquiry.id is not None
    _awaiting(auth_client, inquiry)
    with Session(migrated_engine) as session:
        draft = session.exec(
            select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry.id)
        ).one()
        fallback = datetime(2026, 1, 1, tzinfo=UTC)
        draft.result = {"unreadable": True}
        draft.updated_at = fallback
        session.add(draft)
        session.exec(
            delete(InquiryDraftDecision).where(
                col(InquiryDraftDecision.inquiry_id) == inquiry.id,
                col(InquiryDraftDecision.action) == "approve",
            )
        )
        session.commit()
    _login(auth_client, supervisor)

    response = auth_client.get("/api/supervisor/queue")
    item = response.json()["items"][0]
    assert response.json()["total"] == 1
    assert item["submitted_at"] == fallback.isoformat().replace("+00:00", "Z")
    assert item["review_state"] == "unavailable"
    detail = auth_client.get(f"/api/supervisor/reviews/{inquiry.id}").json()
    assert detail["offer"] is None
    assert detail["offer_unavailable"] is True
    assert detail["allowed_actions"] == ["reject"]


def test_review_after_decision_and_invalid_identifier(
    migrated_engine: Engine,
    auth_client: TestClient,
    supervisor: User,
    make_inquiry: InquiryFactory,
    use_extractor: ExtractorSetter,
) -> None:
    inquiry = _delta(make_inquiry)
    assert inquiry.id is not None
    draft = _awaiting(auth_client, inquiry)
    _login(auth_client, supervisor)
    decided = auth_client.post(
        f"{_path(inquiry.id)}/draft/supervisor-decision",
        json={"updated_at": draft["updated_at"], "action": "reject", "reason": "Poprawka"},
    )
    assert decided.status_code == 200

    before = decided.json()["draft"]["updated_at"]
    with Session(migrated_engine) as session:
        decision_count = len(
            session.exec(
                select(InquiryDraftDecision).where(
                    col(InquiryDraftDecision.inquiry_id) == inquiry.id
                )
            ).all()
        )
    detail = auth_client.get(f"/api/supervisor/reviews/{inquiry.id}")
    assert detail.status_code == 200
    assert detail.json()["review_state"] == "not_awaiting"
    assert detail.json()["allowed_actions"] == []
    assert detail.json()["draft_updated_at"] == before
    assert detail.json()["decisions"][-1]["action"] == "supervisor_reject"
    with Session(migrated_engine) as session:
        stored = session.exec(
            select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry.id)
        ).one()
        decisions_after = session.exec(
            select(InquiryDraftDecision).where(col(InquiryDraftDecision.inquiry_id) == inquiry.id)
        ).all()
    assert stored.updated_at.isoformat().replace("+00:00", "Z") == before
    assert len(decisions_after) == decision_count
    assert auth_client.get("/api/supervisor/reviews/2147483648").status_code == 422
    assert auth_client.get("/api/supervisor/reviews/2147483647").status_code == 404


def test_queue_names_the_customer_and_survives_a_row_that_cannot_be_read(
    auth_client: TestClient,
    supervisor: User,
    make_inquiry: InquiryFactory,
    use_extractor: ExtractorSetter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inquiry = _delta(make_inquiry)
    _awaiting(auth_client, inquiry)
    _login(auth_client, supervisor)

    item = next(
        entry
        for entry in auth_client.get("/api/supervisor/queue").json()["items"]
        if entry["id"] == inquiry.id
    )
    assert item["customer"]

    def broken(*_args: object, **_kwargs: object) -> None:
        raise KeyError("malformed")

    monkeypatch.setattr("app.inquiries.supervisor_queue._policy", broken)

    response = auth_client.get("/api/supervisor/queue")
    assert response.status_code == 200
    unreadable = next(entry for entry in response.json()["items"] if entry["id"] == inquiry.id)
    assert unreadable["review_state"] == "unavailable"
    assert unreadable["attention_rules"] == []
    review = auth_client.get(f"/api/supervisor/reviews/{inquiry.id}")
    assert review.status_code == 200
    assert review.json()["allowed_actions"] == ["reject"]
