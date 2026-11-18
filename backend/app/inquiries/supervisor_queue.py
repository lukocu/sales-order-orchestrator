"""Read projections for the supervisor's approval queue and review screen."""

import logging
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlmodel import Session, col, select

from app.checks.models import InquiryChecks
from app.checks.schema import CheckResults
from app.draft.models import InquiryDraft, InquiryDraftDecision
from app.draft.offer import render_body, render_subject
from app.draft.schema import DecisionSnapshot, DraftOffer, DraftResult, DraftStatus
from app.draft.service import DecisionView, _user_name, policy_in_force
from app.inquiries.models import Inquiry
from app.orchestration.models import InquiryOrchestration
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import ParsedFields
from app.policy.schema import PolicyResult, RuleCode
from app.recommendation.models import InquiryRecommendation
from app.recommendation.pin import is_current

logger = logging.getLogger(__name__)

ReviewState = Literal["actionable", "stale", "unavailable", "not_awaiting"]
AllowedAction = Literal["approve", "reject"]


class AttentionRule(BaseModel):
    code: RuleCode
    verdict: Literal["fail", "not_evaluated"]


class QueueItem(BaseModel):
    id: int
    sender_name: str
    subject: str
    received_at: datetime
    submitted_at: datetime
    submitted_by: int | None
    draft_updated_at: datetime
    attention_rules: list[AttentionRule]
    review_state: ReviewState


class QueueView(BaseModel):
    items: list[QueueItem]
    total: int


class ReviewContext(BaseModel):
    fields: ParsedFields | None
    checks: CheckResults | None
    orchestration: dict[str, Any] | None
    recommendation: dict[str, Any] | None
    policy: PolicyResult | None


class ReviewView(BaseModel):
    inquiry_id: int
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime
    draft_status: DraftStatus | None
    draft_updated_at: datetime | None
    submitted_at: datetime | None
    submitted_by: int | None
    review_state: ReviewState
    allowed_actions: list[AllowedAction]
    offer: DraftOffer | None
    offer_unavailable: bool
    offer_subject: str | None
    offer_body: str | None
    policy: PolicyResult | None
    context: ReviewContext
    decisions: list[DecisionView]


def _submitted(session: Session, draft: InquiryDraft) -> tuple[datetime, int | None]:
    decision = session.exec(
        select(InquiryDraftDecision)
        .where(
            col(InquiryDraftDecision.inquiry_id) == draft.inquiry_id,
            col(InquiryDraftDecision.recommended_at) == draft.recommended_at,
            col(InquiryDraftDecision.action) == "approve",
            col(InquiryDraftDecision.status_after) == "awaiting_supervisor",
        )
        .order_by(col(InquiryDraftDecision.id).desc())
        .limit(1)
    ).first()
    if decision is None:
        return draft.updated_at, None
    return decision.decided_at, decision.decided_by


def _validated_result(draft: InquiryDraft) -> DraftResult | None:
    try:
        return DraftResult.model_validate(draft.result)
    except ValidationError as error:
        logger.error(
            "Stored draft of inquiry %s does not match the schema: %s",
            draft.inquiry_id,
            type(error).__name__,
        )
        return None


def _is_current(session: Session, draft: InquiryDraft, analysis: InquiryAnalysis | None) -> bool:
    if analysis is None:
        return False
    recommendation = session.exec(
        select(InquiryRecommendation).where(
            col(InquiryRecommendation.inquiry_id) == draft.inquiry_id
        )
    ).first()
    return (
        recommendation is not None
        and recommendation.status == "completed"
        and recommendation.recommended_at == draft.recommended_at
        and is_current(session, recommendation, analysis)
    )


def _review_state(
    session: Session,
    draft: InquiryDraft,
    analysis: InquiryAnalysis | None,
    result: DraftResult | None,
    policy: PolicyResult | None,
) -> ReviewState:
    if result is None:
        return "unavailable"
    if not _is_current(session, draft, analysis):
        return "stale"
    if policy is None:
        return "unavailable"
    return "actionable"


def _policy(
    session: Session,
    analysis: InquiryAnalysis | None,
    draft: InquiryDraft,
    result: DraftResult | None,
) -> PolicyResult | None:
    if result is None or analysis is None or not _is_current(session, draft, analysis):
        return None
    try:
        return policy_in_force(session, analysis, draft, result)
    except ValidationError as error:
        logger.error(
            "Stored review data of inquiry %s does not match the schema: %s",
            draft.inquiry_id,
            type(error).__name__,
        )
        return None


def get_queue(session: Session) -> QueueView:
    """Return one row per raw pending draft, including stale/unreadable submissions."""
    drafts = list(
        session.exec(
            select(InquiryDraft).where(col(InquiryDraft.status) == "awaiting_supervisor")
        ).all()
    )
    if not drafts:
        return QueueView(items=[], total=0)

    ids = [draft.inquiry_id for draft in drafts]
    inquiries = {
        inquiry.id: inquiry
        for inquiry in session.exec(select(Inquiry).where(col(Inquiry.id).in_(ids))).all()
    }
    analyses = {
        analysis.inquiry_id: analysis
        for analysis in session.exec(
            select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id).in_(ids))
        ).all()
    }
    decisions = list(
        session.exec(
            select(InquiryDraftDecision)
            .where(
                col(InquiryDraftDecision.inquiry_id).in_(ids),
                col(InquiryDraftDecision.recommended_at).in_(
                    [draft.recommended_at for draft in drafts]
                ),
                col(InquiryDraftDecision.action) == "approve",
                col(InquiryDraftDecision.status_after) == "awaiting_supervisor",
            )
            .order_by(col(InquiryDraftDecision.id).desc())
        ).all()
    )
    # Query above is batched; select the last matching decision per inquiry/recommendation.
    submissions: dict[tuple[int, datetime], InquiryDraftDecision] = {}
    for decision in decisions:
        submissions.setdefault((decision.inquiry_id, decision.recommended_at), decision)

    items: list[QueueItem] = []
    for draft in drafts:
        inquiry = inquiries.get(draft.inquiry_id)
        if inquiry is None:
            continue
        analysis = analyses.get(draft.inquiry_id)
        result = _validated_result(draft)
        policy = _policy(session, analysis, draft, result)
        state = _review_state(session, draft, analysis, result, policy)
        submission = submissions.get((draft.inquiry_id, draft.recommended_at))
        submitted_at = draft.updated_at if submission is None else submission.decided_at
        submitted_by = None if submission is None else submission.decided_by
        attention = (
            []
            if policy is None or state == "stale"
            else [
                AttentionRule(code=rule.code, verdict=rule.verdict)
                for rule in policy.rules
                if rule.verdict in ("fail", "not_evaluated")
            ]
        )
        items.append(
            QueueItem(
                id=draft.inquiry_id,
                sender_name=inquiry.sender_name,
                subject=inquiry.subject,
                received_at=inquiry.received_at,
                submitted_at=submitted_at,
                submitted_by=submitted_by,
                draft_updated_at=draft.updated_at,
                attention_rules=attention,
                review_state=state,
            )
        )
    items.sort(key=lambda item: (item.submitted_at, item.id))
    return QueueView(items=items, total=len(items))


def _history(session: Session, inquiry_id: int, current_at: datetime | None) -> list[DecisionView]:
    rows = session.exec(
        select(InquiryDraftDecision)
        .where(col(InquiryDraftDecision.inquiry_id) == inquiry_id)
        .order_by(col(InquiryDraftDecision.decided_at), col(InquiryDraftDecision.id))
    ).all()
    views: list[DecisionView] = []
    for row in rows:
        try:
            snapshot = DecisionSnapshot.model_validate(row.snapshot)
        except ValidationError as error:
            logger.error(
                "Stored decision of inquiry %s does not match the schema: %s",
                inquiry_id,
                type(error).__name__,
            )
            snapshot = None
        views.append(
            DecisionView(
                action=row.action,
                status_after=row.status_after,
                reason=row.reason,
                decided_by_name=_user_name(session, row.decided_by),
                decided_at=row.decided_at,
                snapshot=snapshot,
                current=row.recommended_at == current_at,
            )
        )
    return views


def get_review(session: Session, inquiry_id: int, viewer_id: int) -> ReviewView | None:
    inquiry = session.get(Inquiry, inquiry_id)
    if inquiry is None:
        return None
    draft = session.exec(
        select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry_id)
    ).first()
    analysis = session.exec(
        select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
    ).first()
    result = None if draft is None else _validated_result(draft)
    policy = None if draft is None else _policy(session, analysis, draft, result)
    state: ReviewState
    if draft is None or draft.status != "awaiting_supervisor":
        state = "not_awaiting"
    else:
        state = _review_state(session, draft, analysis, result, policy)
    submitted_at: datetime | None = None
    submitted_by: int | None = None
    if draft is not None:
        submitted_at, submitted_by = _submitted(session, draft)
    allowed: list[AllowedAction] = []
    if draft is not None and draft.status == "awaiting_supervisor":
        allowed = ["reject"]
        if state == "actionable" and submitted_by != viewer_id:
            # Read permission is advisory; actual decision service remains authoritative.
            allowed.append("approve")
    recommendation = session.exec(
        select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry_id)
    ).first()
    current = bool(
        draft is not None
        and analysis is not None
        and recommendation is not None
        and draft.recommended_at == recommendation.recommended_at
        and is_current(session, recommendation, analysis)
    )
    current_at = recommendation.recommended_at if current and recommendation is not None else None
    context = ReviewContext(
        fields=_json_model(
            analysis.fields if analysis is not None else None, ParsedFields, inquiry_id
        ),
        checks=_read_checks(session, inquiry_id),
        orchestration=_read_json(
            session, InquiryOrchestration, inquiry_id, "result", "orchestration"
        ),
        recommendation=_read_json(
            session, InquiryRecommendation, inquiry_id, "result", "recommendation"
        ),
        policy=policy,
    )
    return ReviewView(
        inquiry_id=inquiry_id,
        sender_name=inquiry.sender_name,
        sender_email=inquiry.sender_email,
        subject=inquiry.subject,
        body=inquiry.body,
        received_at=inquiry.received_at,
        draft_status=None if draft is None else draft.status,
        draft_updated_at=None if draft is None else draft.updated_at,
        submitted_at=submitted_at,
        submitted_by=submitted_by,
        review_state=state,
        allowed_actions=allowed,
        offer=None if result is None else result.offer,
        offer_unavailable=draft is not None and result is None,
        offer_subject=(None if result is None else render_subject(inquiry.subject)),
        offer_body=(
            None if result is None else render_body(result.offer, result.text, inquiry.sender_name)
        ),
        policy=policy,
        context=context,
        decisions=_history(session, inquiry_id, current_at),
    )


def _json_model(raw: Any, model: type[BaseModel], inquiry_id: int) -> Any:
    if raw is None:
        return None
    try:
        return model.model_validate(raw)
    except ValidationError as error:
        logger.error(
            "Stored review data of inquiry %s does not match the schema: %s",
            inquiry_id,
            type(error).__name__,
        )
        return None


def _read_checks(session: Session, inquiry_id: int) -> CheckResults | None:
    row = session.exec(
        select(InquiryChecks).where(col(InquiryChecks.inquiry_id) == inquiry_id)
    ).first()
    return None if row is None else _json_model(row.results, CheckResults, inquiry_id)


def _read_json(
    session: Session,
    model: Any,
    inquiry_id: int,
    field: str,
    label: str,
) -> dict[str, Any] | None:
    row = session.exec(select(model).where(col(model.inquiry_id) == inquiry_id)).first()
    if row is None:
        return None
    value = getattr(row, field)
    if not isinstance(value, dict):
        logger.error("Stored %s data of inquiry %s is not an object", label, inquiry_id)
        return None
    return value
