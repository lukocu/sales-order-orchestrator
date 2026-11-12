"""Draft stage in the inquiry chain: draft after the policy, keep, replace, retry, fall back,
store guard, regenerate and the decision history, in fake mode."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, update
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.checks.rules import CENT
from app.draft import service as draft_service
from app.draft.drafter import (
    FALLBACK_CLOSING,
    FALLBACK_INTRO,
    DrafterFailed,
    DrafterOutput,
    DrafterRateLimited,
    DraftFacts,
    FakeDrafter,
    UnconfiguredDrafter,
)
from app.draft.models import InquiryDraft, InquiryDraftDecision
from app.draft.offer import InvalidEdit, LineEdit, format_amount
from app.draft.schema import DecisionSnapshot, DraftOffer, DraftStatus
from app.draft.service import (
    DraftChanged,
    DraftDecided,
    DraftNotEditable,
    DraftStale,
    NothingToDraft,
    PolicyMissing,
    ReasonRequired,
    decide,
    draft_after_policy,
    edit_draft,
    generate_draft,
    regenerate_draft,
)
from app.inquiries.models import Inquiry
from app.policy.models import InquiryPolicyVerdict
from app.recommendation.models import InquiryRecommendation
from app.tracing.models import StepKind
from app.tracing.pricing import LlmUsage
from tests.conftest import DrafterSetter, ExtractorSetter, InquiryFactory
from tests.test_parsing_extractors import ACME, BIURO_MAX, DELTA, OMEGA

USAGE = LlmUsage(provider="groq", model="openai/gpt-oss-120b", input_tokens=500, output_tokens=80)
MODEL_TEXT = DrafterOutput(
    intro="Dziękujemy za zapytanie, przygotowaliśmy propozycję.",
    closing="Prosimy o potwierdzenie.",
    usage=None,
)
WITH_DIGIT = DrafterOutput(intro="Oferujemy 80 sztuk.", closing="Pozdrawiamy.", usage=None)


def _analysis_path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/analysis"


def _path(inquiry_id: int | None) -> str:
    return f"/api/inquiries/{inquiry_id}/draft"


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


def _read(client: TestClient, inquiry: Inquiry) -> dict[str, Any]:
    body: dict[str, Any] = client.get(_analysis_path(inquiry.id)).json()
    return body


def _stored(engine: Engine, inquiry: Inquiry) -> InquiryDraft | None:
    with Session(engine) as session:
        return session.exec(
            select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry.id)
        ).first()


def _set_draft(engine: Engine, inquiry: Inquiry, **values: Any) -> None:
    with Session(engine) as session:
        session.execute(
            update(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry.id).values(**values)
        )
        session.commit()


def _chosen(recommendation: dict[str, Any]) -> dict[str, Any]:
    option_id = recommendation["choice"]["option_id"]
    chosen: dict[str, Any] = next(o for o in recommendation["options"] if o["id"] == option_id)
    return chosen


def _steps(view: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(s["name"], s["kind"], s["status"]) for s in view["run"]["steps"]]


def _add_decision(
    engine: Engine,
    inquiry: Inquiry,
    draft: dict[str, Any],
    user: User,
    *,
    status_after: DraftStatus = "ready_to_send",
) -> None:
    """A decision row as `decide` writes it, without its checks."""
    assert inquiry.id is not None
    snapshot = DecisionSnapshot(
        offer=DraftOffer.model_validate(draft["offer"]),
        policy_outcome="no_approval_needed",
        failing_rules=[],
    )
    with Session(engine) as session:
        session.add(
            InquiryDraftDecision(
                inquiry_id=inquiry.id,
                recommended_at=_recommended_at_of_draft(engine, inquiry),
                action="approve",
                status_after=status_after,
                reason="Zgodne z polityką",
                decided_by=user.id,
                decided_at=datetime.now(UTC),
                snapshot=snapshot.model_dump(mode="json"),
            )
        )
        session.commit()


def _recommended_at_of_draft(engine: Engine, inquiry: Inquiry) -> datetime:
    row = _stored(engine, inquiry)
    assert row is not None
    return row.recommended_at


class StubDrafter:
    """Drafter for tests: raises or answers the queued items in order, then the template
    text; `on_write` runs inside each call (to change the database meanwhile)."""

    name = "stub"

    def __init__(
        self,
        *,
        queue: list[Exception | DrafterOutput] | None = None,
        step_kind: StepKind = "llm",
        on_write: Callable[[], None] | None = None,
    ) -> None:
        self._queue = list(queue or [])
        self.step_kind: StepKind = step_kind
        self._on_write = on_write
        self.calls = 0

    def write(self, facts: DraftFacts) -> DrafterOutput:
        self.calls += 1
        if self._on_write is not None:
            self._on_write()
        if self._queue:
            item = self._queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return FakeDrafter().write(facts)


def _transient(usage: LlmUsage | None = None) -> DrafterFailed:
    return DrafterFailed("Provider timed out", transient=True, usage=usage)


# --- Seed scenarios ---------------------------------------------------------------------


@pytest.mark.parametrize("seed", [ACME, OMEGA, DELTA], ids=["acme", "omega", "delta"])
def test_exception_gets_a_draft_with_the_chosen_options_numbers(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    make_inquiry: InquiryFactory,
    migrated_engine: Engine,
    seed: tuple[str, str, date],
) -> None:
    inquiry = _inquiry(make_inquiry, seed)

    body = _analyze(auth_client, inquiry)

    draft = body["draft"]
    assert draft is not None
    assert (draft["status"], draft["stale"], draft["text_source"]) == ("draft", False, "model")
    chosen = _chosen(body["recommendation"])
    offer = draft["offer"]
    assert (offer["option_id"], offer["kind"], offer["edited"]) == (
        chosen["id"],
        chosen["kind"],
        False,
    )
    for name in ("value", "cost", "margin_percent", "fulfilled_on", "meets_deadline"):
        assert offer[name] == chosen[name]
    assert [
        (line["product_code"], line["quantity"], line["unit_price"]) for line in offer["lines"]
    ] == [(line["product_code"], line["quantity"], line["unit_price"]) for line in chosen["lines"]]
    assert draft["subject"] == f"Re: {seed[0]}"
    assert draft["body"].startswith("Dzień dobry,")
    assert f"Razem: {format_amount(Decimal(offer['value']))} PLN netto." in draft["body"]
    for line in offer["lines"]:
        assert f"{line['quantity']} szt." in draft["body"]
    assert draft["why"]["justification"] == body["recommendation"]["choice"]["justification"]
    labels = {s["code"]: s["label"] for s in chosen["signals"]}
    assert draft["why"]["signals"] == [
        labels[code] for code in body["recommendation"]["choice"]["cited_signals"]
    ]
    # The verdict in force of an offer as recommended is the policy stage's.
    assert draft["policy"]["outcome"] == body["policy"]["outcome"]
    assert draft["policy"]["rules"] == body["policy"]["rules"]
    # Its own run with one template step, after the policy's.
    assert draft["run"]["id"] != body["policy"]["run"]["id"]
    assert _steps(draft) == [("draft", "deterministic", "ok")]
    assert body["decisions"] == []
    row = _stored(migrated_engine, inquiry)
    assert row is not None
    assert row.status == "draft"
    assert row.recommended_at == datetime.fromisoformat(body["recommendation"]["recommended_at"])
    assert row.result["drafter"] == "fake"


def test_delta_draft_carries_the_supervisor_verdict(
    auth_client: TestClient, use_extractor: ExtractorSetter, make_inquiry: InquiryFactory
) -> None:
    draft = _analyze(auth_client, _inquiry(make_inquiry, DELTA))["draft"]

    assert draft["policy"]["outcome"] == "requires_supervisor"
    assert draft["status"] == "draft"


def test_standard_inquiry_has_no_draft(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    biuro_max: Inquiry,
    migrated_engine: Engine,
) -> None:
    body = _analyze(auth_client, biuro_max)

    assert body["checks"]["outcome"] == "standard"
    assert (body["draft"], body["decisions"]) == (None, [])
    assert _stored(migrated_engine, biuro_max) is None


# --- Chain and pins ---------------------------------------------------------------------


def test_policy_rerun_keeps_the_draft(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_drafter: DrafterSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    before = _analyze(auth_client, acme)["draft"]
    # As if the salesperson had rejected it.
    _set_draft(migrated_engine, acme, status="rejected")
    drafter = StubDrafter()
    use_drafter(drafter)

    response = auth_client.post(f"/api/inquiries/{acme.id}/policy")

    assert response.status_code == 200
    assert drafter.calls == 0  # a kept draft costs no model call
    draft = response.json()["draft"]
    assert draft["status"] == "rejected"
    assert (draft["updated_at"], draft["run"]["id"]) == (before["updated_at"], before["run"]["id"])
    assert draft["stale"] is False


def test_policy_rerun_drafts_a_missing_draft(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    _analyze(auth_client, acme)
    with Session(migrated_engine) as session:
        session.execute(delete(InquiryDraft).where(col(InquiryDraft.inquiry_id) == acme.id))
        session.commit()

    response = auth_client.post(f"/api/inquiries/{acme.id}/policy")

    assert response.status_code == 200
    assert response.json()["draft"]["status"] == "draft"


def test_new_recommendation_replaces_the_draft_and_keeps_decisions(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    before = _analyze(auth_client, acme)["draft"]
    _add_decision(migrated_engine, acme, before, test_user)
    _set_draft(migrated_engine, acme, status="ready_to_send")
    (decision,) = _read(auth_client, acme)["decisions"]
    assert (decision["action"], decision["status_after"], decision["current"]) == (
        "approve",
        "ready_to_send",
        True,
    )
    assert (decision["reason"], decision["decided_by_name"]) == ("Zgodne z polityką", "Test User")
    assert decision["snapshot"]["offer"] == before["offer"]

    response = auth_client.post(f"/api/inquiries/{acme.id}/recommendation")

    assert response.status_code == 200
    body = response.json()
    draft = body["draft"]
    assert (draft["status"], draft["stale"]) == ("draft", False)
    assert draft["drafted_at"] != before["drafted_at"]
    assert draft["run"]["id"] != before["run"]["id"]
    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.recommended_at == datetime.fromisoformat(body["recommendation"]["recommended_at"])
    (kept,) = body["decisions"]
    assert kept["current"] is False  # made on an earlier version of the recommendation
    assert kept["decided_at"] == decision["decided_at"]


def test_removing_the_exception_drops_the_draft_but_not_the_decisions(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    analysis = _analyze(auth_client, acme)
    _add_decision(migrated_engine, acme, analysis["draft"], test_user, status_after="rejected")

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
    assert corrected["draft"] is None
    assert _stored(migrated_engine, acme) is None
    (decision,) = corrected["decisions"]
    assert (decision["status_after"], decision["current"]) == ("rejected", False)


def test_draft_of_another_recommendation_is_stale(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    _analyze(auth_client, acme)
    _set_draft(migrated_engine, acme, recommended_at=datetime(2020, 1, 1, tzinfo=UTC))

    assert _read(auth_client, acme)["draft"]["stale"] is True


def test_unedited_draft_without_a_verdict_is_stale(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    _analyze(auth_client, acme)
    with Session(migrated_engine) as session:
        session.execute(
            delete(InquiryPolicyVerdict).where(col(InquiryPolicyVerdict.inquiry_id) == acme.id)
        )
        session.commit()

    draft = _read(auth_client, acme)["draft"]

    assert (draft["policy"], draft["stale"]) == (None, True)


def test_stored_draft_not_matching_schema_is_hidden(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _analyze(auth_client, acme)
    _set_draft(migrated_engine, acme, result={"removed_field": "x"})

    response = auth_client.get(_analysis_path(acme.id))

    assert response.status_code == 200
    assert response.json()["draft"] is None
    assert "ValidationError" in caplog.text
    assert "removed_field" not in caplog.text


def test_unexpected_error_after_policy_keeps_the_analysis(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_drafter: DrafterSetter,
    acme: Inquiry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    use_drafter(StubDrafter(queue=[RuntimeError("secret inquiry content")]))

    body = _analyze(auth_client, acme)

    assert body["policy"] is not None
    assert body["draft"] is None
    assert "RuntimeError" in caplog.text
    assert "secret inquiry content" not in caplog.text


# --- Retry and fallback -----------------------------------------------------------------


def test_chain_gives_the_drafter_one_attempt_then_the_fallback(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_drafter: DrafterSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    drafter = StubDrafter(queue=[_transient(USAGE)])
    use_drafter(drafter)

    draft = _analyze(auth_client, acme)["draft"]

    assert drafter.calls == 1
    assert (draft["status"], draft["text_source"]) == ("draft", "fallback")
    assert FALLBACK_INTRO in draft["body"]
    assert FALLBACK_CLOSING in draft["body"]
    (step,) = draft["run"]["steps"]
    assert (step["name"], step["kind"], step["status"]) == ("draft", "llm", "failed")
    assert (step["input_tokens"], step["output_tokens"]) == (500, 80)
    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.result["text"]["error"] == "unavailable"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (DrafterFailed("Bad response", transient=False), "failed"),
        (DrafterRateLimited("slow down"), "rate_limited"),
    ],
    ids=["permanent", "rate-limited"],
)
def test_regenerate_falls_back_with_the_error_code(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    error: Exception,
    code: str,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    drafter = StubDrafter(queue=[error, error])

    regenerate_draft(migrated_engine, acme.id, drafter, retry_delay_s=0)

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.result["text"] == {
        "intro": FALLBACK_INTRO,
        "closing": FALLBACK_CLOSING,
        "source": "fallback",
        "error": code,
    }
    # Only transient errors are retried.
    assert drafter.calls == (2 if code == "rate_limited" else 1)


def test_unconfigured_drafter_falls_back(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    use_drafter: DrafterSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    use_drafter(UnconfiguredDrafter("groq"))

    draft = _analyze(auth_client, acme)["draft"]

    assert draft["text_source"] == "fallback"
    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.result["text"]["error"] == "not_configured"


def test_transient_error_is_retried_as_draft_2(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    drafter = StubDrafter(queue=[_transient(), MODEL_TEXT])

    regenerate_draft(migrated_engine, acme.id, drafter, retry_delay_s=0)

    draft = _read(auth_client, acme)["draft"]
    assert drafter.calls == 2
    assert draft["text_source"] == "model"
    assert MODEL_TEXT.intro in draft["body"]
    assert _steps(draft) == [("draft", "llm", "failed"), ("draft#2", "llm", "ok")]


def test_text_with_a_digit_is_retried_then_replaced_by_the_fallback(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    drafter = StubDrafter(queue=[WITH_DIGIT, WITH_DIGIT])

    regenerate_draft(migrated_engine, acme.id, drafter, retry_delay_s=0)

    draft = _read(auth_client, acme)["draft"]
    assert draft["text_source"] == "fallback"
    assert "Oferujemy 80" not in draft["body"]
    assert _steps(draft) == [("draft", "llm", "failed"), ("draft#2", "llm", "failed")]
    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.result["text"]["error"] == "text_has_digit"


def test_text_with_a_digit_then_a_valid_one_is_the_models(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)

    regenerate_draft(
        migrated_engine, acme.id, StubDrafter(queue=[WITH_DIGIT, MODEL_TEXT]), retry_delay_s=0
    )

    draft = _read(auth_client, acme)["draft"]
    assert draft["text_source"] == "model"
    assert _steps(draft) == [("draft", "llm", "failed"), ("draft#2", "llm", "ok")]


# --- Store guard ------------------------------------------------------------------------


def test_draft_written_during_the_call_is_not_overwritten(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    inquiry_id = acme.id
    stored = _analyze(auth_client, acme)["draft"]
    recommended_at = _recommended_at_of_draft(migrated_engine, acme)
    with Session(migrated_engine) as session:
        session.execute(delete(InquiryDraft).where(col(InquiryDraft.inquiry_id) == acme.id))
        session.commit()

    def drafted_meanwhile() -> None:
        # Another request stores (and the salesperson decides) a draft of this recommendation.
        now = datetime.now(UTC)
        with Session(migrated_engine) as session:
            session.add(
                InquiryDraft(
                    inquiry_id=inquiry_id,
                    run_id=stored["run"]["id"],
                    recommended_at=recommended_at,
                    status="awaiting_supervisor",
                    result=_result_of(stored),
                    drafted_at=now,
                    updated_at=now,
                )
            )
            session.commit()

    generate_draft(migrated_engine, acme.id, StubDrafter(on_write=drafted_meanwhile))

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert (row.status, row.run_id) == ("awaiting_supervisor", stored["run"]["id"])


def test_regenerate_does_not_overwrite_a_decision_made_during_the_call(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    stored = _analyze(auth_client, acme)["draft"]

    def decided_meanwhile() -> None:
        _set_draft(migrated_engine, acme, status="ready_to_send", updated_at=datetime.now(UTC))

    regenerate_draft(
        migrated_engine, acme.id, StubDrafter(on_write=decided_meanwhile), retry_delay_s=0
    )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert (row.status, row.run_id) == ("ready_to_send", stored["run"]["id"])


def test_draft_of_a_replaced_recommendation_is_dropped(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    assert acme.id is not None
    stored = _analyze(auth_client, acme)["draft"]

    def recommended_again() -> None:
        with Session(migrated_engine) as session:
            session.execute(
                update(InquiryRecommendation)
                .where(col(InquiryRecommendation.inquiry_id) == acme.id)
                .values(recommended_at=datetime.now(UTC))
            )
            session.commit()

    regenerate_draft(
        migrated_engine, acme.id, StubDrafter(on_write=recommended_again), retry_delay_s=0
    )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.run_id == stored["run"]["id"]  # the draft for the old recommendation is dropped


def test_outdated_call_does_not_delete_a_current_draft(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert acme.id is not None
    stored = _analyze(auth_client, acme)["draft"]

    def nothing(session: Session, inquiry_id: int) -> None:
        # A call that read its inputs while the recommendation was being replaced.
        raise NothingToDraft

    monkeypatch.setattr(draft_service, "_read_inputs", nothing)

    draft_after_policy(migrated_engine, acme.id, FakeDrafter())

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.run_id == stored["run"]["id"]  # pinned to the current recommendation: kept


def _result_of(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "drafter": "fake",
        "offer": view["offer"],
        "text": {
            "intro": FALLBACK_INTRO,
            "closing": FALLBACK_CLOSING,
            "source": "fallback",
            "error": None,
        },
        "policy": None,
    }


# --- Regenerate -------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["ready_to_send", "awaiting_supervisor"])
def test_decided_draft_cannot_be_regenerated(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    status: DraftStatus,
) -> None:
    assert acme.id is not None
    _analyze(auth_client, acme)
    _set_draft(migrated_engine, acme, status=status)

    with pytest.raises(DraftDecided):
        regenerate_draft(migrated_engine, acme.id, FakeDrafter())

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "Draft already decided"}
    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.status == status


@pytest.mark.parametrize("status", ["draft", "rejected"])
def test_regenerate_resets_the_draft(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    status: DraftStatus,
) -> None:
    before = _analyze(auth_client, acme)["draft"]
    _set_draft(migrated_engine, acme, status=status)

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 200
    body = response.json()
    draft = body["draft"]
    assert (draft["status"], draft["stale"]) == ("draft", False)
    assert draft["offer"] == before["offer"]
    assert draft["updated_at"] != before["updated_at"]
    assert draft["run"]["id"] != before["run"]["id"]
    assert auth_client.get(_analysis_path(acme.id)).json() == body


def test_decided_draft_of_an_earlier_recommendation_can_be_regenerated(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    _analyze(auth_client, acme)
    _set_draft(
        migrated_engine,
        acme,
        status="ready_to_send",
        recommended_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    assert _read(auth_client, acme)["draft"]["stale"] is True

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert (draft["status"], draft["stale"]) == ("draft", False)


def test_regenerate_without_a_draft_drafts(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
) -> None:
    _analyze(auth_client, acme)
    with Session(migrated_engine) as session:
        session.execute(delete(InquiryDraft).where(col(InquiryDraft.inquiry_id) == acme.id))
        session.commit()

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 200
    assert response.json()["draft"]["status"] == "draft"


# --- API --------------------------------------------------------------------------------


def test_standard_inquiry_is_409(
    auth_client: TestClient, use_extractor: ExtractorSetter, biuro_max: Inquiry
) -> None:
    _analyze(auth_client, biuro_max)

    response = auth_client.post(_path(biuro_max.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "Nothing to draft"}


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
    use_drafter: DrafterSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stored = _analyze(auth_client, acme)["draft"]
    use_drafter(StubDrafter(queue=[RuntimeError("secret inquiry content")]))
    caplog.clear()

    response = auth_client.post(_path(acme.id))

    assert response.status_code == 500
    assert response.json() == {"detail": "Drafting failed"}
    assert "RuntimeError" in caplog.text
    assert str(acme.id) in caplog.text
    assert "secret inquiry content" not in caplog.text
    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.run_id == stored["run"]["id"]


def test_without_session_is_401(client: TestClient) -> None:
    response = client.post(_path(1))

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


# --- Decisions --------------------------------------------------------------------------


def _auth(user: User) -> AuthUser:
    return AuthUser.from_user(user)


def _token(draft: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(draft["updated_at"])


def _edits(draft: dict[str, Any], *, discount: Decimal | None = None) -> list[LineEdit]:
    """The draft's lines as edits; with `discount` (percent) every unit price is cut to that
    much below its list price."""
    return [
        LineEdit(
            product_code=line["product_code"],
            quantity=line["quantity"],
            unit_price=(
                Decimal(line["unit_price"])
                if discount is None
                else (Decimal(line["list_price"]) * (100 - discount) / 100).quantize(CENT)
            ),
        )
        for line in draft["offer"]["lines"]
    ]


def _decisions(engine: Engine, inquiry: Inquiry) -> list[InquiryDraftDecision]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(InquiryDraftDecision)
                .where(col(InquiryDraftDecision.inquiry_id) == inquiry.id)
                .order_by(col(InquiryDraftDecision.id))
            ).all()
        )


def test_approve_without_approval_needed_is_ready_to_send(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    assert draft["policy"]["outcome"] == "no_approval_needed"

    decide(
        migrated_engine,
        acme.id,
        _auth(test_user),
        updated_at=_token(draft),
        action="approve",
        reason="  ",
    )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.status == "ready_to_send"
    assert row.updated_at != _token(draft)
    (decision,) = _decisions(migrated_engine, acme)
    assert (decision.action, decision.status_after, decision.reason) == (
        "approve",
        "ready_to_send",
        None,  # a blank comment is no comment
    )
    assert decision.decided_by == test_user.id
    assert decision.decided_at == row.updated_at
    assert decision.recommended_at == row.recommended_at
    snapshot = DecisionSnapshot.model_validate(decision.snapshot)
    assert snapshot.offer == DraftOffer.model_validate(draft["offer"])
    assert (snapshot.policy_outcome, snapshot.failing_rules) == ("no_approval_needed", [])


def test_approve_with_supervisor_verdict_awaits_the_supervisor(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    make_inquiry: InquiryFactory,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    delta = _inquiry(make_inquiry, DELTA)
    assert delta.id is not None
    draft = _analyze(auth_client, delta)["draft"]

    decide(
        migrated_engine,
        delta.id,
        _auth(test_user),
        updated_at=_token(draft),
        action="approve",
        reason="Klient strategiczny",
    )

    row = _stored(migrated_engine, delta)
    assert row is not None
    assert row.status == "awaiting_supervisor"
    (decision,) = _decisions(migrated_engine, delta)
    assert (decision.status_after, decision.reason) == (
        "awaiting_supervisor",
        "Klient strategiczny",
    )
    snapshot = DecisionSnapshot.model_validate(decision.snapshot)
    assert snapshot.policy_outcome == "requires_supervisor"
    assert "discount" in snapshot.failing_rules


def test_edit_without_changes_keeps_the_stage_outcome(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    body = _analyze(auth_client, acme)
    draft = body["draft"]

    edit_draft(
        migrated_engine,
        acme.id,
        _auth(test_user),
        updated_at=_token(draft),
        option_id=draft["offer"]["option_id"],
        lines=_edits(draft),
        reason="Bez zmian",
    )

    edited = _read(auth_client, acme)["draft"]
    assert edited["offer"]["edited"] is True
    assert edited["offer"]["value"] == draft["offer"]["value"]
    assert edited["policy"]["outcome"] == body["policy"]["outcome"]
    assert [r["verdict"] for r in edited["policy"]["rules"]] == [
        r["verdict"] for r in body["policy"]["rules"]
    ]


def test_edit_recomputes_the_offer_and_its_policy(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    edits = _edits(draft, discount=Decimal("20"))
    edits[0] = edits[0].model_copy(update={"quantity": edits[0].quantity + 5})

    edit_draft(
        migrated_engine,
        acme.id,
        _auth(test_user),
        updated_at=_token(draft),
        option_id=draft["offer"]["option_id"],
        lines=edits,
        reason=" Rabat negocjowany ",
    )

    view = _read(auth_client, acme)
    edited = view["draft"]
    assert (edited["status"], edited["stale"]) == ("draft", False)
    offer = edited["offer"]
    assert offer["edited"] is True
    expected_value = sum((e.unit_price * e.quantity for e in edits), Decimal("0"))
    assert Decimal(offer["value"]) == expected_value
    assert offer["covered_quantity"] == sum(e.quantity for e in edits)
    assert Decimal(offer["margin_percent"]) < Decimal(draft["offer"]["margin_percent"])
    assert f"Razem: {format_amount(expected_value)} PLN netto." in edited["body"]
    # The edit's own verdict: the offered discount fails the discount rule.
    assert edited["policy"]["outcome"] == "requires_supervisor"
    discount = next(r for r in edited["policy"]["rules"] if r["code"] == "discount")
    assert discount["verdict"] == "fail"
    assert Decimal(discount["actual"]) >= Decimal("19.99")
    # The policy stage's verdict of the offer as recommended is untouched.
    assert view["policy"]["outcome"] == "no_approval_needed"
    (decision,) = view["decisions"]
    assert (decision["action"], decision["status_after"], decision["reason"]) == (
        "edit",
        "draft",
        "Rabat negocjowany",
    )
    assert decision["decided_by_name"] == "Test User"
    assert decision["snapshot"]["offer"] == offer
    assert "discount" in decision["snapshot"]["failing_rules"]

    # Approving the edited offer follows its own verdict.
    decide(
        migrated_engine,
        acme.id,
        _auth(test_user),
        updated_at=_token(edited),
        action="approve",
        reason=None,
    )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.status == "awaiting_supervisor"
    assert [d.action for d in _decisions(migrated_engine, acme)] == ["edit", "approve"]


def test_reject_needs_a_reason_and_rejects(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    user = _auth(test_user)

    for reason in (None, "", "   "):
        with pytest.raises(ReasonRequired):
            decide(
                migrated_engine,
                acme.id,
                user,
                updated_at=_token(draft),
                action="reject",
                reason=reason,
            )
    assert _decisions(migrated_engine, acme) == []

    decide(
        migrated_engine,
        acme.id,
        user,
        updated_at=_token(draft),
        action="reject",
        reason="Klient wycofał zapytanie",
    )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.status == "rejected"
    (decision,) = _decisions(migrated_engine, acme)
    assert (decision.action, decision.status_after, decision.reason) == (
        "reject",
        "rejected",
        "Klient wycofał zapytanie",
    )


def test_edit_needs_a_reason(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]

    with pytest.raises(ReasonRequired):
        edit_draft(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            option_id=draft["offer"]["option_id"],
            lines=_edits(draft),
            reason=" ",
        )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.result["offer"]["edited"] is False


def test_invalid_edits_change_nothing(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    option_id = draft["offer"]["option_id"]
    edits = _edits(draft)
    invalid: list[tuple[str, list[LineEdit]]] = [
        ("no-such-option", edits),
        (option_id, [*edits, edits[0]]),
        (option_id, [edits[0].model_copy(update={"quantity": 0}), *edits[1:]]),
        (option_id, [edits[0].model_copy(update={"unit_price": Decimal("0")}), *edits[1:]]),
    ]

    for edited_option, lines in invalid:
        with pytest.raises(InvalidEdit):
            edit_draft(
                migrated_engine,
                acme.id,
                _auth(test_user),
                updated_at=_token(draft),
                option_id=edited_option,
                lines=lines,
                reason="Zmiana",
            )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert (row.updated_at, row.result["offer"]["edited"]) == (_token(draft), False)
    assert _decisions(migrated_engine, acme) == []


def test_edit_can_switch_to_another_option(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    body = _analyze(auth_client, acme)
    draft = body["draft"]
    others = [
        o for o in body["recommendation"]["options"] if o["id"] != draft["offer"]["option_id"]
    ]
    assert others, "the ACME recommendation has more than one option"
    other = others[0]
    lines = [
        LineEdit(
            product_code=line["product_code"],
            quantity=line["quantity"],
            unit_price=Decimal(line["unit_price"]),
        )
        for line in other["lines"]
    ]

    edit_draft(
        migrated_engine,
        acme.id,
        _auth(test_user),
        updated_at=_token(draft),
        option_id=other["id"],
        lines=lines,
        reason="Inna opcja",
    )

    offer = _read(auth_client, acme)["draft"]["offer"]
    assert (offer["option_id"], offer["kind"], offer["edited"]) == (
        other["id"],
        other["kind"],
        True,
    )
    assert offer["value"] == other["value"]


def test_changed_draft_is_refused(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    _set_draft(migrated_engine, acme, updated_at=datetime.now(UTC))

    with pytest.raises(DraftChanged):
        decide(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            action="approve",
            reason=None,
        )
    with pytest.raises(DraftChanged):
        edit_draft(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            option_id=draft["offer"]["option_id"],
            lines=_edits(draft),
            reason="Zmiana",
        )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.status == "draft"
    assert _decisions(migrated_engine, acme) == []


@pytest.mark.parametrize("status", ["ready_to_send", "awaiting_supervisor", "rejected"])
def test_decided_draft_cannot_be_changed(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
    status: DraftStatus,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    _set_draft(migrated_engine, acme, status=status)

    with pytest.raises(DraftNotEditable):
        decide(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            action="reject",
            reason="Za późno",
        )
    with pytest.raises(DraftNotEditable):
        edit_draft(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            option_id=draft["offer"]["option_id"],
            lines=_edits(draft),
            reason="Zmiana",
        )
    assert _decisions(migrated_engine, acme) == []


def test_decision_after_a_decision_is_refused(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    decide(
        migrated_engine,
        acme.id,
        _auth(test_user),
        updated_at=_token(draft),
        action="approve",
        reason=None,
    )
    approved = _read(auth_client, acme)["draft"]

    with pytest.raises(DraftNotEditable):
        decide(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(approved),
            action="reject",
            reason="Pomyłka",
        )
    assert len(_decisions(migrated_engine, acme)) == 1


def test_stale_draft_is_refused(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    _set_draft(migrated_engine, acme, recommended_at=datetime(2020, 1, 1, tzinfo=UTC))

    with pytest.raises(DraftStale):
        decide(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            action="approve",
            reason=None,
        )
    with pytest.raises(DraftStale):
        edit_draft(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            option_id=draft["offer"]["option_id"],
            lines=_edits(draft),
            reason="Zmiana",
        )
    assert _decisions(migrated_engine, acme) == []


@pytest.mark.parametrize("verdict", ["missing", "stale"])
def test_approve_without_a_current_verdict_is_refused(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
    verdict: str,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    with Session(migrated_engine) as session:
        where = col(InquiryPolicyVerdict.inquiry_id) == acme.id
        if verdict == "missing":
            session.execute(delete(InquiryPolicyVerdict).where(where))
        else:
            session.execute(
                update(InquiryPolicyVerdict)
                .where(where)
                .values(recommended_at=datetime(2020, 1, 1, tzinfo=UTC))
            )
        session.commit()

    with pytest.raises(PolicyMissing):
        decide(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            action="approve",
            reason=None,
        )

    row = _stored(migrated_engine, acme)
    assert row is not None
    assert row.status == "draft"
    assert _decisions(migrated_engine, acme) == []


def test_decision_without_a_draft_is_nothing_to_draft(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    acme: Inquiry,
    migrated_engine: Engine,
    test_user: User,
) -> None:
    assert acme.id is not None
    draft = _analyze(auth_client, acme)["draft"]
    with Session(migrated_engine) as session:
        session.execute(delete(InquiryDraft).where(col(InquiryDraft.inquiry_id) == acme.id))
        session.commit()

    with pytest.raises(NothingToDraft):
        decide(
            migrated_engine,
            acme.id,
            _auth(test_user),
            updated_at=_token(draft),
            action="approve",
            reason=None,
        )
