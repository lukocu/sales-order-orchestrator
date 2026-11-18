"""Stable translation metadata, including old persisted JSONB. No business reevaluation."""

from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.draft.models import InquiryDraft, InquiryDraftDecision
from app.draft.schema import DecisionSnapshot, DraftResult
from app.policy.models import InquiryPolicyVerdict
from app.policy.rules import (
    evaluate_credit,
    evaluate_discount,
    evaluate_margin,
    evaluate_order_value,
)
from app.policy.schema import PolicyResult
from app.recommendation.confidence import ConfidenceContext, assess
from app.recommendation.models import InquiryRecommendation
from app.recommendation.options import build_options
from app.recommendation.schema import RecommendationResult, Signal
from tests.conftest import ExtractorSetter, InquiryFactory
from tests.test_draft_models import _offer
from tests.test_parsing_extractors import ACME
from tests.test_policy_core import _credit, _discount
from tests.test_recommendation_core import _acme, _by_id

D = Decimal


@pytest.mark.parametrize(
    ("margin", "minimum", "code"),
    [
        ("20", None, "margin_threshold_missing"),
        ("20", "20", "margin_within_minimum"),
        ("19.99", "20", "margin_below_minimum"),
    ],
)
def test_margin_reason_codes(margin: str, minimum: str | None, code: str) -> None:
    assert evaluate_margin(D(margin), None if minimum is None else D(minimum)).reason_code == code


@pytest.mark.parametrize(
    ("value", "maximum", "code"),
    [
        ("20", None, "order_value_threshold_missing"),
        ("20", "20", "order_value_within_maximum"),
        ("20.01", "20", "order_value_above_maximum"),
    ],
)
def test_order_value_reason_codes(value: str, maximum: str | None, code: str) -> None:
    assert (
        evaluate_order_value(D(value), None if maximum is None else D(maximum)).reason_code == code
    )


@pytest.mark.parametrize(
    ("kind", "value", "standard", "status", "list_price", "maximum", "code"),
    [
        ("none", None, None, "skipped", None, "15", "discount_check_skipped"),
        ("discount_percent", None, "5", "ok", None, "15", "requested_discount_missing"),
        ("target_price", None, "5", "ok", "100", "15", "target_price_missing"),
        ("target_price", "80", "5", "ok", None, "15", "target_list_price_missing"),
        ("target_price", "80", "5", "ok", "0", "15", "target_list_price_missing"),
        ("none", None, None, "ok", None, "15", "standard_discount_missing"),
        ("none", None, "5", "ok", None, None, "discount_threshold_missing"),
        ("discount_percent", "15", "5", "ok", None, "15", "requested_discount_within_maximum"),
        ("discount_percent", "16", "5", "ok", None, "15", "requested_discount_above_maximum"),
        ("target_price", "85", "5", "ok", "100", "15", "target_discount_within_maximum"),
        ("target_price", "84", "5", "ok", "100", "15", "target_discount_above_maximum"),
        ("none", None, "15", "ok", None, "15", "standard_discount_within_maximum"),
        ("best_price", None, "16", "ok", None, "15", "standard_discount_above_maximum"),
    ],
)
def test_requested_discount_reason_codes(
    kind: str,
    value: str | None,
    standard: str | None,
    status: str,
    list_price: str | None,
    maximum: str | None,
    code: str,
) -> None:
    discount = _discount(kind, value, standard, status)  # type: ignore[arg-type]
    rule = evaluate_discount(
        discount,
        None if list_price is None else D(list_price),
        None if maximum is None else D(maximum),
    )
    assert rule.reason_code == code


@pytest.mark.parametrize(
    ("offered", "maximum", "code"),
    [
        ("15", "15", "offered_discount_within_maximum"),
        ("16", "15", "offered_discount_above_maximum"),
        ("16", None, "discount_threshold_missing"),
    ],
)
def test_edited_offer_keeps_deciding_reason(offered: str, maximum: str | None, code: str) -> None:
    rule = evaluate_discount(_discount(), None, None if maximum is None else D(maximum), D(offered))
    assert rule.reason_code == code
    requested = evaluate_discount(_discount("discount_percent", "25"), None, D("15"), D("10"))
    assert requested.reason_code == "requested_discount_above_maximum"
    assert requested.actual == D("25")


@pytest.mark.parametrize(
    ("limit", "balance", "status", "code"),
    [
        (None, None, "skipped", "credit_check_skipped"),
        (None, None, "blocked", "credit_blocked"),
        (None, "10", "ok", "credit_data_missing"),
        ("100", None, "ok", "credit_data_missing"),
        ("100", "0", "ok", "credit_within_limit"),
        ("100", "0.01", "ok", "credit_over_limit"),
    ],
)
def test_credit_reason_codes(
    limit: str | None, balance: str | None, status: str, code: str
) -> None:
    assert evaluate_credit(_credit(limit, balance, status), D("100")).reason_code == code


def test_dynamic_signal_params_describe_their_own_option_and_product() -> None:
    options = _by_id(build_options(_acme()))
    partial = options["stock"]
    assert next(s for s in partial.signals if s.code == "incomplete_coverage").params == {
        "covered": 50,
        "requested": 80,
    }
    supplier = next(o for o in options.values() if o.kind == "other_source")
    assert next(s for s in supplier.signals if s.code == "deadline_missed").params == {
        "fulfilled_on": "2026-11-09",
        "deadline": "2026-11-06",
    }
    option = options["stock+ABC-110"]
    # Two substitutes can share one signal code; parameters belong to each occurrence.
    second = option.lines[-1].model_copy(update={"product_code": "SECOND"})
    option = option.model_copy(update={"lines": [*option.lines, second]})
    context = ConfidenceContext(
        deadline=date(2026, 11, 6),
        consent="confirmed",
        task_statuses={},
        compatibility={"ABC-110": "full", "SECOND": "partial"},
        history=None,
        uncertain_inputs=["quantity"],
    )
    band, signals = assess(option, context)
    assert [(s.code, s.params) for s in signals if s.code.startswith("compat_")] == [
        ("compat_full", {"product_code": "ABC-110"}),
        ("compat_partial", {"product_code": "SECOND"}),
    ]
    assert band == "MEDIUM"
    assert any(s.code == "uncertain_input:quantity" for s in signals)
    assert any(s.code == "not_checked:customer-history" for s in signals)


@pytest.mark.parametrize("params", [{"bad": True}, {"bad": None}, {"bad": []}, {"bad": {}}])
def test_signal_params_reject_non_scalar_or_boolean_values(params: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Signal(code="future", polarity="info", label="Original", params=params)


def test_signal_params_defaults_are_independent_and_round_trip() -> None:
    first = Signal(code="old", polarity="info", label="Original")
    second = Signal.model_validate({"code": "old", "polarity": "info", "label": "Original"})
    first.params["count"] = 1
    assert second.params == {}
    signal = Signal(
        code="future",
        polarity="info",
        label="Original",
        params={"integer": 2, "fraction": 1.5, "text": "ABC"},
    )
    assert Signal.model_validate_json(signal.model_dump_json()) == signal


@pytest.mark.parametrize("legacy", [True, False])
def test_jsonb_reads_preserve_recommendation_policy_draft_and_history(
    auth_client: TestClient,
    use_extractor: ExtractorSetter,
    make_inquiry: InquiryFactory,
    migrated_engine: Engine,
    legacy: bool,
) -> None:
    subject, body, reference = ACME
    inquiry = make_inquiry(
        subject=subject,
        body=body,
        received_at=datetime(reference.year, reference.month, reference.day, tzinfo=UTC),
    )
    assert inquiry.id is not None
    path = f"/api/inquiries/{inquiry.id}/analysis"
    assert auth_client.post(path).status_code == 200
    with Session(migrated_engine) as session:
        recommendation = session.exec(
            select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry.id)
        ).one()
        policy = session.exec(
            select(InquiryPolicyVerdict).where(col(InquiryPolicyVerdict.inquiry_id) == inquiry.id)
        ).one()
        draft = session.exec(
            select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry.id)
        ).one()
        recommendation_data = deepcopy(recommendation.result)
        policy_data = deepcopy(policy.result)
        if legacy:
            for option in recommendation_data["options"]:
                for signal in option["signals"]:
                    signal.pop("params")
            for rule in policy_data["rules"]:
                rule.pop("reason_code")
        recommendation.result = recommendation_data
        policy.result = policy_data
        draft_data = deepcopy(draft.result)
        draft_data["policy"] = deepcopy(policy_data)
        draft.result = draft_data
        snapshot_data = DecisionSnapshot(
            offer=_offer(), policy_outcome="requires_supervisor", failing_rules=["discount"]
        ).model_dump(mode="json")
        if legacy:
            snapshot_data.pop("not_evaluated_rules")
        decision = InquiryDraftDecision(
            inquiry_id=inquiry.id,
            recommended_at=draft.recommended_at,
            action="edit",
            status_after="draft",
            decided_at=datetime.now(UTC),
            snapshot=snapshot_data,
        )
        session.add_all([recommendation, policy, draft, decision])
        session.commit()
        saved = deepcopy([recommendation.result, policy.result, draft.result, decision.snapshot])
        ids = recommendation.id, policy.id, draft.id, decision.id
    # Full model and real API reads must accept both generations without rewriting JSONB.
    assert RecommendationResult.model_validate(saved[0]).options
    assert PolicyResult.model_validate(saved[1]).rules
    assert DraftResult.model_validate(saved[2]).policy is not None
    assert DecisionSnapshot.model_validate(saved[3]).failing_rules == ["discount"]
    response = auth_client.get(path)
    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"] is not None
    assert result["policy"] is not None
    assert result["draft"] is not None
    with Session(migrated_engine) as session:
        assert [
            session.get_one(InquiryRecommendation, ids[0]).result,
            session.get_one(InquiryPolicyVerdict, ids[1]).result,
            session.get_one(InquiryDraft, ids[2]).result,
            session.get_one(InquiryDraftDecision, ids[3]).snapshot,
        ] == saved
