"""HTTP layer of the salesperson's decisions: PUT /draft (edit) and POST /draft/decision
(approve, reject), in fake mode."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, update
from sqlmodel import Session, col

from app.draft.models import InquiryDraft
from app.inquiries.models import Inquiry
from app.policy.models import InquiryPolicyVerdict
from tests.conftest import ExtractorSetter, InquiryFactory
from tests.test_parsing_extractors import ACME, BIURO_MAX, DELTA


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


def _draft_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/draft"


def _decision_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/draft/decision"


def _analyze(client: TestClient, inquiry: Inquiry) -> dict[str, Any]:
    response = client.post(f"/api/inquiries/{inquiry.id}/analysis")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def _edit_body(
    draft: dict[str, Any], *, unit_price: str | None = None, reason: str | None = "Negocjacje"
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "updated_at": draft["updated_at"],
        "option_id": draft["offer"]["option_id"],
        "lines": [
            {
                "product_code": line["product_code"],
                "quantity": line["quantity"],
                "unit_price": line["unit_price"] if unit_price is None else unit_price,
            }
            for line in draft["offer"]["lines"]
        ],
    }
    if reason is not None:
        body["reason"] = reason
    return body


def _set_draft(engine: Engine, inquiry: Inquiry, **values: Any) -> None:
    with Session(engine) as session:
        session.execute(
            update(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry.id).values(**values)
        )
        session.commit()


# --- Approve and reject -----------------------------------------------------------------


def test_approve_acme_is_ready_to_send(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    draft = _analyze(auth_client, acme)["draft"]

    response = auth_client.post(
        _decision_path(acme.id), json={"updated_at": draft["updated_at"], "action": "approve"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["status"] == "ready_to_send"
    assert body["draft"]["updated_at"] != draft["updated_at"]
    (decision,) = body["decisions"]
    assert (decision["action"], decision["status_after"], decision["reason"]) == (
        "approve",
        "ready_to_send",
        None,
    )
    assert decision["decided_by_name"] == "Test User"  # from the session
    assert decision["current"] is True
    assert decision["snapshot"]["policy_outcome"] == "no_approval_needed"
    assert auth_client.get(f"/api/inquiries/{acme.id}/analysis").json() == body


def test_approve_delta_awaits_the_supervisor(
    auth_client: TestClient, use_extractor: ExtractorSetter, make_inquiry: InquiryFactory
) -> None:
    delta = _inquiry(make_inquiry, DELTA)
    draft = _analyze(auth_client, delta)["draft"]

    response = auth_client.post(
        _decision_path(delta.id),
        json={"updated_at": draft["updated_at"], "action": "approve", "reason": "Ważny klient"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["status"] == "awaiting_supervisor"
    (decision,) = body["decisions"]
    assert decision["reason"] == "Ważny klient"
    assert "discount" in decision["snapshot"]["failing_rules"]


def test_reject_with_a_reason(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    draft = _analyze(auth_client, acme)["draft"]

    response = auth_client.post(
        _decision_path(acme.id),
        json={"updated_at": draft["updated_at"], "action": "reject", "reason": "Za drogo"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["status"] == "rejected"
    (decision,) = body["decisions"]
    assert (decision["action"], decision["reason"]) == ("reject", "Za drogo")


@pytest.mark.parametrize("reason", [None, "", "   "], ids=["missing", "empty", "blank"])
def test_reject_without_a_reason_is_422(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    reason: str | None,
) -> None:
    draft = _analyze(auth_client, acme)["draft"]
    request: dict[str, Any] = {"updated_at": draft["updated_at"], "action": "reject"}
    if reason is not None:
        request["reason"] = reason

    response = auth_client.post(_decision_path(acme.id), json=request)

    assert response.status_code == 422
    assert response.json() == {"detail": "Reason is required"}
    after = auth_client.get(f"/api/inquiries/{acme.id}/analysis").json()
    assert (after["draft"]["status"], after["decisions"]) == ("draft", [])


def test_unknown_action_is_422(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    draft = _analyze(auth_client, acme)["draft"]

    response = auth_client.post(
        _decision_path(acme.id), json={"updated_at": draft["updated_at"], "action": "send"}
    )

    assert response.status_code == 422


# --- Edit -------------------------------------------------------------------------------


def test_edit_with_a_large_discount_requires_the_supervisor(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    draft = _analyze(auth_client, acme)["draft"]
    list_price = Decimal(draft["offer"]["lines"][0]["list_price"])
    cut = str((list_price * Decimal("0.80")).quantize(Decimal("0.01")))

    response = auth_client.put(_draft_path(acme.id), json=_edit_body(draft, unit_price=cut))

    assert response.status_code == 200
    body = response.json()
    edited = body["draft"]
    assert (edited["status"], edited["offer"]["edited"]) == ("draft", True)
    assert all(line["unit_price"] == cut for line in edited["offer"]["lines"])
    assert edited["policy"]["outcome"] == "requires_supervisor"
    discount = next(r for r in edited["policy"]["rules"] if r["code"] == "discount")
    assert discount["verdict"] == "fail"
    (decision,) = body["decisions"]
    assert (decision["action"], decision["status_after"], decision["reason"]) == (
        "edit",
        "draft",
        "Negocjacje",
    )
    assert decision["decided_by_name"] == "Test User"

    approved = auth_client.post(
        _decision_path(acme.id), json={"updated_at": edited["updated_at"], "action": "approve"}
    )

    assert approved.status_code == 200
    assert approved.json()["draft"]["status"] == "awaiting_supervisor"


@pytest.mark.parametrize("reason", [None, " "], ids=["missing", "blank"])
def test_edit_without_a_reason_is_422(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    reason: str | None,
) -> None:
    draft = _analyze(auth_client, acme)["draft"]

    response = auth_client.put(_draft_path(acme.id), json=_edit_body(draft, reason=reason))

    assert response.status_code == 422
    assert response.json() == {"detail": "Reason is required"}


def test_invalid_edit_is_422(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    draft = _analyze(auth_client, acme)["draft"]

    zero_price = auth_client.put(_draft_path(acme.id), json=_edit_body(draft, unit_price="0"))
    unknown_option = auth_client.put(
        _draft_path(acme.id), json={**_edit_body(draft), "option_id": "no-such-option"}
    )

    assert zero_price.status_code == 422
    assert zero_price.json() == {"detail": "Unit price must be above zero"}
    assert unknown_option.status_code == 422
    assert unknown_option.json() == {"detail": "Option is not one of the recommendation's options"}
    after = auth_client.get(f"/api/inquiries/{acme.id}/analysis").json()
    assert (after["draft"]["offer"]["edited"], after["decisions"]) == (False, [])


def test_edit_with_an_unknown_line_field_is_422(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    draft = _analyze(auth_client, acme)["draft"]
    request = _edit_body(draft)
    request["lines"][0]["discount"] = "10"

    response = auth_client.put(_draft_path(acme.id), json=request)

    assert response.status_code == 422


# --- Conflicts --------------------------------------------------------------------------


def test_changed_draft_is_409(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    draft = _analyze(auth_client, acme)["draft"]
    edited = auth_client.put(_draft_path(acme.id), json=_edit_body(draft))
    assert edited.status_code == 200

    # Both requests carry the token read before the edit.
    approve = auth_client.post(
        _decision_path(acme.id), json={"updated_at": draft["updated_at"], "action": "approve"}
    )
    edit = auth_client.put(_draft_path(acme.id), json=_edit_body(draft))

    for response in (approve, edit):
        assert response.status_code == 409
        assert response.json() == {"detail": "Draft changed, reload"}


def test_decided_draft_is_409(
    auth_client: TestClient, use_extractor: ExtractorSetter, acme: Inquiry
) -> None:
    draft = _analyze(auth_client, acme)["draft"]
    approved = auth_client.post(
        _decision_path(acme.id), json={"updated_at": draft["updated_at"], "action": "approve"}
    ).json()["draft"]

    reject = auth_client.post(
        _decision_path(acme.id),
        json={"updated_at": approved["updated_at"], "action": "reject", "reason": "Pomyłka"},
    )
    edit = auth_client.put(
        _draft_path(acme.id), json={**_edit_body(draft), "updated_at": approved["updated_at"]}
    )

    for response in (reject, edit):
        assert response.status_code == 409
        assert response.json() == {"detail": "Draft cannot be changed"}


def test_stale_draft_is_409(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    draft = _analyze(auth_client, acme)["draft"]
    _set_draft(migrated_engine, acme, recommended_at=datetime(2020, 1, 1, tzinfo=UTC))

    response = auth_client.post(
        _decision_path(acme.id), json={"updated_at": draft["updated_at"], "action": "approve"}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Draft is stale"}


def test_approve_without_a_verdict_is_409(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    draft = _analyze(auth_client, acme)["draft"]
    with Session(migrated_engine) as session:
        session.execute(
            delete(InquiryPolicyVerdict).where(col(InquiryPolicyVerdict.inquiry_id) == acme.id)
        )
        session.commit()

    response = auth_client.post(
        _decision_path(acme.id), json={"updated_at": draft["updated_at"], "action": "approve"}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Policy verdict missing"}


def test_inquiry_without_a_draft_is_409(
    auth_client: TestClient, use_extractor: ExtractorSetter, make_inquiry: InquiryFactory
) -> None:
    biuro_max = _inquiry(make_inquiry, BIURO_MAX)
    _analyze(auth_client, biuro_max)
    token = datetime.now(UTC).isoformat()

    approve = auth_client.post(
        _decision_path(biuro_max.id), json={"updated_at": token, "action": "approve"}
    )
    edit = auth_client.put(
        _draft_path(biuro_max.id),
        json={"updated_at": token, "option_id": "x", "lines": [], "reason": "Zmiana"},
    )

    for response in (approve, edit):
        assert response.status_code == 409
        assert response.json() == {"detail": "Nothing to draft"}


# --- Not found and auth -----------------------------------------------------------------


def test_without_analysis_is_404(auth_client: TestClient, acme: Inquiry) -> None:
    response = auth_client.post(
        _decision_path(acme.id),
        json={"updated_at": datetime.now(UTC).isoformat(), "action": "approve"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No analysis yet"}


def test_unknown_inquiry_is_404(auth_client: TestClient) -> None:
    response = auth_client.put(
        _draft_path(2_147_483_647),
        json={
            "updated_at": datetime.now(UTC).isoformat(),
            "option_id": "x",
            "lines": [],
            "reason": "Zmiana",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Inquiry not found"}


def test_naive_token_is_422(auth_client: TestClient) -> None:
    response = auth_client.post(
        _decision_path(1), json={"updated_at": "2026-11-12T10:00:00", "action": "approve"}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("method", ["put", "post"])
def test_without_session_is_401(client: TestClient, method: str) -> None:
    path = _draft_path(1) if method == "put" else _decision_path(1)

    response = client.request(method.upper(), path, json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
