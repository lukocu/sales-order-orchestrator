"""Generate, store and read the reply draft of an inquiry, and read its decision history.

Mirrors `app.policy.service`: inputs are read from the current data in one short session (the
stored recommendation and its chosen option, the list prices of the option's products, the
inquiry and its check result), the drafter writes the paragraphs in its own tracing run (one
`draft` step per attempt, `draft#2` for the retry) and the draft is written once, in another
short session that locks the analysis row.

The draft is pinned to the recommendation by its `recommended_at`. A draft that already
exists for the current recommendation is never replaced by the chain (re-running the policy
keeps an edit or a decision); a new recommendation replaces it, and only "Regenerate draft"
resets a draft of the current recommendation, when its `updated_at` did not change since it
was read. Decisions are append-only and outlive the draft they were made on.

Only the recommendation's models and pin are imported here, never
`app.recommendation.service`, which calls this module. Logs carry the error class and the
inquiry id only, never inquiry content.
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine, delete
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.checks.models import Product
from app.checks.schema import CheckResults
from app.checks.service import analysis_version, current_checks, lock_analysis
from app.draft.drafter import (
    FALLBACK_CLOSING,
    FALLBACK_INTRO,
    Drafter,
    DrafterError,
    DrafterFailed,
    DrafterNotConfigured,
    DrafterRateLimited,
    DraftFacts,
    TextRejected,
    validate_text,
)
from app.draft.models import InquiryDraft, InquiryDraftDecision
from app.draft.offer import (
    InvalidEdit,
    LineEdit,
    apply_edit,
    offer_from_option,
    offer_policy_inputs,
    render_body,
    render_subject,
)
from app.draft.schema import (
    DecisionAction,
    DecisionSnapshot,
    DraftOffer,
    DraftResult,
    DraftStatus,
    DraftText,
    TextSource,
)
from app.inquiries.models import Inquiry
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import ParsedFields
from app.policy.models import InquiryPolicyVerdict
from app.policy.rules import evaluate
from app.policy.schema import PolicyResult
from app.policy.service import get_policy_view, load_thresholds
from app.recommendation.models import InquiryRecommendation
from app.recommendation.pin import is_current
from app.recommendation.schema import RecommendationOption, RecommendationResult
from app.tracing import RunHandle, run
from app.tracing.summary import RunSummary, get_run_summary

logger = logging.getLogger(__name__)

SUBJECT_TYPE = "inquiry"
DRAFTER_ATTEMPTS = 2
DRAFTER_RETRY_DELAY_S = 1.0
# Statuses of a draft the salesperson has decided on; "Regenerate draft" refuses them while
# the draft belongs to the current recommendation.
DECIDED: tuple[DraftStatus, ...] = ("ready_to_send", "awaiting_supervisor")


class NothingToDraft(Exception):
    """No current recommendation with a chosen option: none stored, not `completed`, no
    choice or chosen option, not computed from the current data, or a product of the chosen
    option without a list price."""


class DraftDecided(Exception):
    """The draft of the current recommendation was approved; it cannot be regenerated."""


class DraftChanged(Exception):
    """The draft was written since the salesperson read it (another `updated_at`)."""


class DraftNotEditable(Exception):
    """The draft is no longer in status `draft`: it was approved or rejected."""


class DraftStale(Exception):
    """The draft no longer belongs to the current recommendation (recommended again, or the
    recommendation is not computed from the current data)."""


class PolicyMissing(Exception):
    """Approve without a verdict in force: the policy stage's verdict of the offer as
    recommended is missing or stale, or an edited offer carries no verdict."""


class ReasonRequired(ValueError):
    """An edit or a rejection without a reason (missing or blank)."""


class DraftWhy(BaseModel):
    """The "Why this recommendation?" section: the justification and its cited signals."""

    justification: str
    signals: list[str]  # Polish labels of the cited signals of the chosen option


class DraftView(BaseModel):
    status: DraftStatus
    offer: DraftOffer
    subject: str
    body: str  # rendered on read from the offer and the paragraphs
    text_source: TextSource
    why: DraftWhy | None  # None when the stored recommendation has no chosen option
    # The verdict in force: the edit's own for an edited offer, the policy stage's otherwise.
    policy: PolicyResult | None
    # built from another recommendation, the recommendation is not current, or (offer as
    # recommended) the policy stage's verdict is missing or stale
    stale: bool
    drafted_at: datetime
    updated_at: datetime
    run: RunSummary | None  # None when the run could not be traced or was deleted


class DecisionView(BaseModel):
    action: DecisionAction
    status_after: DraftStatus
    reason: str | None
    decided_by_name: str | None
    decided_at: datetime
    snapshot: DecisionSnapshot
    current: bool  # made on a draft of the current recommendation


@dataclass(frozen=True)
class _StoredDraft:
    recommended_at: datetime
    status: DraftStatus
    updated_at: datetime


@dataclass(frozen=True)
class _Inputs:
    recommendation_id: int
    recommended_at: datetime  # identifies the recommendation the draft is built from
    offer: DraftOffer
    facts: DraftFacts
    draft: _StoredDraft | None  # the stored draft when the inputs were read


def generate_draft(
    engine: Engine,
    inquiry_id: int,
    drafter: Drafter,
    *,
    attempts: int = DRAFTER_ATTEMPTS,
    retry_delay_s: float = DRAFTER_RETRY_DELAY_S,
) -> None:
    """Draft the current recommendation's chosen option in a new run and store it, unless a
    draft of that recommendation exists by then.

    Raises `NothingToDraft` when there is no current recommendation with a chosen option,
    after dropping a stored draft that no longer belongs to one. A failing drafter or a
    rejected text never fails the draft: after `attempts` the fixed fallback text is stored.
    Unexpected errors propagate after the run is recorded as failed; the stored draft stays
    as it was.
    """
    inputs = _inputs_or_drop(engine, inquiry_id)
    _generate(engine, inquiry_id, drafter, inputs, attempts, retry_delay_s, replacing=None)


def draft_after_policy(engine: Engine, inquiry_id: int, drafter: Drafter) -> None:
    """After a policy evaluation: draft a new recommendation, else drop a draft of old data.

    A draft of the current recommendation is kept as it is (its edit or decision survives a
    re-run of the policy). Runs inside the chain's requests, so the drafter gets a single
    attempt. Never raises: unexpected errors are logged (class and inquiry id only) and leave
    the stored draft as it was.
    """
    try:
        inputs = _inputs_or_drop(engine, inquiry_id)
        if inputs.draft is not None and inputs.draft.recommended_at == inputs.recommended_at:
            return
        _generate(engine, inquiry_id, drafter, inputs, 1, DRAFTER_RETRY_DELAY_S, replacing=None)
    except NothingToDraft:
        pass  # a draft of old data was already dropped
    except Exception as error:
        logger.warning("Drafting failed for inquiry %s: %s", inquiry_id, type(error).__name__)


def regenerate_draft(
    engine: Engine,
    inquiry_id: int,
    drafter: Drafter,
    *,
    attempts: int = DRAFTER_ATTEMPTS,
    retry_delay_s: float = DRAFTER_RETRY_DELAY_S,
) -> None:
    """Draft the current recommendation again: the offer as recommended, status `draft`.

    Allowed without a draft, for a `draft` or `rejected` one and for a draft of another
    recommendation. Raises `DraftDecided` for a `ready_to_send` or `awaiting_supervisor`
    draft of the current recommendation and `NothingToDraft` as `generate_draft`. The new
    draft is not stored when the draft read here changed meanwhile (an edit or a decision
    wins).
    """
    inputs = _inputs_or_drop(engine, inquiry_id)
    stored = inputs.draft
    if (
        stored is not None
        and stored.recommended_at == inputs.recommended_at
        and stored.status in DECIDED
    ):
        raise DraftDecided
    _generate(
        engine,
        inquiry_id,
        drafter,
        inputs,
        attempts,
        retry_delay_s,
        replacing=None if stored is None else stored.updated_at,
    )


# --- Decisions --------------------------------------------------------------------------


def edit_draft(
    engine: Engine,
    inquiry_id: int,
    user: AuthUser,
    *,
    updated_at: datetime,
    option_id: str,
    lines: Sequence[LineEdit],
    reason: str | None,
) -> None:
    """Replace the draft's offer by an option of the current recommendation with new
    quantities and unit prices of its lines, and evaluate the policy for that offer.

    The edited offer carries its own verdict (the discount rule also judges the offered
    prices). The status stays `draft` and an `edit` decision is appended. Raises
    `ReasonRequired`, `NothingToDraft` without a draft, `DraftChanged`, `DraftNotEditable`,
    `DraftStale` and `InvalidEdit` (unknown option or lines not matching it); nothing is
    written then.
    """
    reason = _required(reason)
    with Session(engine) as session:
        analysis, row, result, recommendation = _locked_draft(session, inquiry_id, updated_at)
        option = next((o for o in recommendation.options if o.id == option_id), None)
        if option is None:
            raise InvalidEdit("Option is not one of the recommendation's options")
        list_prices = _list_prices(session, {line.product_code for line in option.lines})
        if list_prices is None:
            logger.error("Draft of inquiry %s: a product of the edited option is gone", inquiry_id)
            raise NothingToDraft
        offer = apply_edit(option, lines, list_prices)
        checks = current_checks(session, inquiry_id, analysis_version(analysis))
        if checks is None:
            raise DraftStale
        policy = evaluate(
            offer_policy_inputs(offer, CheckResults.model_validate(checks.results)),
            load_thresholds(session),
        )
        row.result = result.model_copy(update={"offer": offer, "policy": policy}).model_dump(
            mode="json"
        )
        _decide(session, row, user, "edit", "draft", reason, offer, policy)


def decide(
    engine: Engine,
    inquiry_id: int,
    user: AuthUser,
    *,
    updated_at: datetime,
    action: Literal["approve", "reject"],
    reason: str | None,
) -> None:
    """Approve or reject the draft and append the decision with what it was about.

    Approve sets `ready_to_send` when the verdict in force needs no approval and
    `awaiting_supervisor` otherwise; the verdict in force is the edit's own for an edited
    offer and the policy stage's current verdict for the offer as recommended. Reject sets
    `rejected` and needs a reason. Raises `ReasonRequired`, `NothingToDraft` without a draft,
    `DraftChanged`, `DraftNotEditable`, `DraftStale` and `PolicyMissing` (approve without a
    verdict in force); nothing is written then.
    """
    reason = _required(reason) if action == "reject" else _optional(reason)
    with Session(engine) as session:
        _, row, result, _ = _locked_draft(session, inquiry_id, updated_at)
        policy = _policy_in_force(session, row, result)
        status_after: DraftStatus
        if action == "reject":
            status_after = "rejected"
        elif policy is None:
            raise PolicyMissing
        elif policy.outcome == "no_approval_needed":
            status_after = "ready_to_send"
        else:
            status_after = "awaiting_supervisor"
        _decide(session, row, user, action, status_after, reason, result.offer, policy)


def get_draft_view(session: Session, analysis: InquiryAnalysis) -> DraftView | None:
    """The stored draft for the analysis' inquiry; None when there is none.

    Also None when the stored result no longer matches `DraftResult` (schema changed without
    a data migration): the analysis stays readable and the draft can be regenerated.
    """
    row = session.exec(
        select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == analysis.inquiry_id)
    ).first()
    if row is None:
        return None
    try:
        result = DraftResult.model_validate(row.result)
    except ValidationError as error:
        # Class and inquiry id only: the validation message would quote the stored values.
        logger.error(
            "Stored draft of inquiry %s does not match the schema: %s",
            analysis.inquiry_id,
            type(error).__name__,
        )
        return None
    inquiry = session.get_one(Inquiry, analysis.inquiry_id)
    recommendation = _recommendation(session, analysis.inquiry_id)
    recommendation_current = (
        recommendation is not None
        and recommendation.recommended_at == row.recommended_at
        and is_current(session, recommendation, analysis)
    )
    why = None if recommendation is None else _why(analysis.inquiry_id, recommendation)

    policy: PolicyResult | None
    if result.offer.edited:
        policy = result.policy
        policy_stale = False
    else:
        stage = get_policy_view(session, analysis)
        policy = (
            None
            if stage is None
            else PolicyResult(
                option_id=stage.option_id,
                rules=stage.rules,
                outcome=stage.outcome,
                thresholds_are_examples=stage.thresholds_are_examples,
            )
        )
        policy_stale = stage is None or stage.stale
    return DraftView(
        status=row.status,
        offer=result.offer,
        subject=render_subject(inquiry.subject),
        body=render_body(result.offer, result.text, inquiry.sender_name),
        text_source=result.text.source,
        why=why,
        policy=policy,
        stale=not recommendation_current or policy_stale,
        drafted_at=row.drafted_at,
        updated_at=row.updated_at,
        run=None if row.run_id is None else get_run_summary(session, row.run_id),
    )


def get_decision_views(session: Session, analysis: InquiryAnalysis) -> list[DecisionView]:
    """Every decision on the inquiry's drafts, oldest first, also of earlier recommendations.

    A decision whose snapshot no longer matches `DecisionSnapshot` is left out (logged).
    """
    inquiry_id = analysis.inquiry_id
    rows = session.exec(
        select(InquiryDraftDecision)
        .where(col(InquiryDraftDecision.inquiry_id) == inquiry_id)
        .order_by(col(InquiryDraftDecision.decided_at), col(InquiryDraftDecision.id))
    ).all()
    if not rows:
        return []
    recommendation = _recommendation(session, inquiry_id)
    current_at = (
        recommendation.recommended_at
        if recommendation is not None and is_current(session, recommendation, analysis)
        else None
    )
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
            continue
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


# --- Inputs -----------------------------------------------------------------------------


def _inputs_or_drop(engine: Engine, inquiry_id: int) -> _Inputs:
    try:
        with Session(engine) as session:
            return _read_inputs(session, inquiry_id)
    except NothingToDraft:
        _drop_outdated(engine, inquiry_id)
        raise


def _recommendation(session: Session, inquiry_id: int) -> InquiryRecommendation | None:
    return session.exec(
        select(InquiryRecommendation).where(col(InquiryRecommendation.inquiry_id) == inquiry_id)
    ).first()


def _chosen(result: RecommendationResult) -> RecommendationOption | None:
    if result.choice is None:
        return None
    option_id = result.choice.option_id
    return next((o for o in result.options if o.id == option_id), None)


def _why(inquiry_id: int, recommendation: InquiryRecommendation) -> DraftWhy | None:
    try:
        result = RecommendationResult.model_validate(recommendation.result)
    except ValidationError as error:
        logger.error(
            "Stored recommendation result of inquiry %s does not match the schema: %s",
            inquiry_id,
            type(error).__name__,
        )
        return None
    option = _chosen(result)
    if result.choice is None or option is None:
        return None
    labels = {s.code: s.label for s in option.signals}
    return DraftWhy(
        justification=result.choice.justification,
        signals=[labels[code] for code in result.choice.cited_signals if code in labels],
    )


def _read_inputs(session: Session, inquiry_id: int) -> _Inputs:
    analysis = session.exec(
        select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
    ).first()
    if analysis is None:
        raise NothingToDraft
    recommendation = _recommendation(session, inquiry_id)
    if recommendation is None or recommendation.status != "completed":
        raise NothingToDraft
    assert recommendation.id is not None
    try:
        result = RecommendationResult.model_validate(recommendation.result)
    except ValidationError as error:
        # Hidden in the view as well; the recommendation has to be re-run first.
        logger.error(
            "Stored recommendation result of inquiry %s does not match the schema: %s",
            inquiry_id,
            type(error).__name__,
        )
        raise NothingToDraft from None
    option = _chosen(result)
    if result.choice is None or option is None:
        raise NothingToDraft
    # The same pin as the recommendation view: analysis version, check result, orchestration.
    if not is_current(session, recommendation, analysis):
        raise NothingToDraft
    checks = current_checks(session, inquiry_id, analysis_version(analysis))
    if checks is None:
        raise NothingToDraft
    customer = CheckResults.model_validate(checks.results).customer.name

    codes = {line.product_code for line in option.lines}
    list_prices: dict[str, Decimal] = {
        product.code: product.list_price
        for product in session.exec(select(Product).where(col(Product.code).in_(codes))).all()
    }
    if not codes <= list_prices.keys():
        # Options are built from catalogue products; a deleted product leaves nothing to draft.
        logger.error("Draft of inquiry %s: a product of the chosen option is gone", inquiry_id)
        raise NothingToDraft
    inquiry = session.get_one(Inquiry, inquiry_id)
    why = _why(inquiry_id, recommendation)
    facts = DraftFacts(
        customer=customer or ParsedFields.model_validate(analysis.fields).customer,
        sender_name=inquiry.sender_name,
        subject=inquiry.subject,
        option_kind=option.kind,
        meets_deadline=option.meets_deadline,
        has_substitute=any(line.source == "substitute_stock" for line in option.lines),
        has_supplier=any(line.source == "supplier" for line in option.lines),
        signals=[] if why is None else why.signals,
        justification=result.choice.justification,
    )
    draft = session.exec(
        select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry_id)
    ).first()
    return _Inputs(
        recommendation_id=recommendation.id,
        recommended_at=recommendation.recommended_at,
        offer=offer_from_option(option, list_prices),
        facts=facts,
        draft=(
            None
            if draft is None
            else _StoredDraft(
                recommended_at=draft.recommended_at,
                status=draft.status,
                updated_at=draft.updated_at,
            )
        ),
    )


# --- Drafting ---------------------------------------------------------------------------


def _generate(
    engine: Engine,
    inquiry_id: int,
    drafter: Drafter,
    inputs: _Inputs,
    attempts: int,
    retry_delay_s: float,
    *,
    replacing: datetime | None,
) -> None:
    with run(engine, subject_type=SUBJECT_TYPE, subject_id=str(inquiry_id)) as traced:
        text = _write(traced, drafter, inquiry_id, inputs.facts, attempts, retry_delay_s)
    result = DraftResult(drafter=drafter.name, offer=inputs.offer, text=text)
    _store(engine, inquiry_id, inputs, traced.id, result, replacing=replacing)


def _write(
    traced: RunHandle,
    drafter: Drafter,
    inquiry_id: int,
    facts: DraftFacts,
    attempts: int,
    retry_delay_s: float,
) -> DraftText:
    """The drafter's paragraphs; a transient error or a rejected text is retried as
    `draft#2` while attempts remain, then the fallback text is used."""
    for attempt in range(1, attempts + 1):
        name = "draft" if attempt == 1 else f"draft#{attempt}"
        try:
            with traced.step(name, kind=drafter.step_kind) as step:
                try:
                    output = drafter.write(facts)
                except DrafterError as error:
                    # The provider may have billed the call before it failed.
                    if error.usage is not None:
                        step.record_usage(error.usage)
                    raise
                if output.usage is not None:
                    step.record_usage(output.usage)
                validate_text(output)
        except DrafterError as error:
            if error.transient and attempt < attempts:
                time.sleep(retry_delay_s)
                continue
            logger.warning(
                "Draft of inquiry %s: %s failed with %s", inquiry_id, name, type(error).__name__
            )
            return _fallback(_drafter_error_code(error))
        except TextRejected as rejected:
            logger.warning("Draft of inquiry %s: %s rejected (%s)", inquiry_id, name, rejected.code)
            if attempt < attempts:
                continue
            return _fallback(rejected.code)
        return DraftText(intro=output.intro, closing=output.closing, source="model")
    raise AssertionError("unreachable")  # pragma: no cover


def _fallback(code: str) -> DraftText:
    return DraftText(intro=FALLBACK_INTRO, closing=FALLBACK_CLOSING, source="fallback", error=code)


def _drafter_error_code(error: DrafterError) -> str:
    if isinstance(error, DrafterNotConfigured):
        return "not_configured"
    if isinstance(error, DrafterRateLimited):
        return "rate_limited"
    if isinstance(error, DrafterFailed) and error.transient:
        return "unavailable"
    return "failed"


# --- Storage ----------------------------------------------------------------------------


def _store(
    engine: Engine,
    inquiry_id: int,
    inputs: _Inputs,
    run_id: int | None,
    result: DraftResult,
    *,
    replacing: datetime | None,
) -> None:
    """Write the draft if its recommendation is still the current one.

    Without `replacing` an existing draft of the same recommendation is kept (written
    meanwhile by another request, or edited or decided). With `replacing` (regenerate) the
    stored draft is replaced only while its `updated_at` is still that value.
    """
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "run_id": run_id,
        "recommended_at": inputs.recommended_at,
        "status": "draft",
        "result": result.model_dump(mode="json"),
        "drafted_at": now,
        "updated_at": now,
    }
    statement = insert(InquiryDraft).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["inquiry_id"],
        set_={name: statement.excluded[name] for name in values if name != "inquiry_id"},
    )
    with Session(engine) as session:
        analysis = lock_analysis(session, inquiry_id)
        if analysis is None:
            return  # the inquiry was deleted meanwhile
        recommendation = _recommendation(session, inquiry_id)
        if (
            recommendation is None
            or recommendation.id != inputs.recommendation_id
            or recommendation.status != "completed"
            or recommendation.recommended_at != inputs.recommended_at
        ):
            return  # recommended again, failed or deleted meanwhile: that chain decides
        if not is_current(session, recommendation, analysis):
            return  # re-checked or orchestrated again meanwhile: that chain decides
        stored = session.exec(
            select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry_id)
        ).first()
        if stored is not None:
            if replacing is not None:
                if stored.updated_at != replacing:
                    return  # edited, decided or drafted again meanwhile: that change wins
            elif stored.recommended_at == inputs.recommended_at:
                return  # drafted meanwhile for this recommendation: never overwritten
        session.exec(statement)
        session.commit()


def _drop_outdated(engine: Engine, inquiry_id: int) -> None:
    """Delete the stored draft when it no longer belongs to a current recommendation.

    That is when the stored recommendation is gone, not `completed`, recommended again
    (another `recommended_at`) or not computed from the current data. The decisions stay.
    A draft of the current recommendation is kept, so an older call never deletes the draft
    of a newer run.
    """
    with Session(engine) as session:
        analysis = lock_analysis(session, inquiry_id)
        if analysis is None:
            return  # the inquiry was deleted; its draft cascades
        draft = session.exec(
            select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry_id)
        ).first()
        if draft is None:
            return
        recommendation = _recommendation(session, inquiry_id)
        outdated = (
            recommendation is None
            or recommendation.status != "completed"
            or recommendation.recommended_at != draft.recommended_at
            or not is_current(session, recommendation, analysis)
        )
        if outdated:
            session.exec(delete(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry_id))
            session.commit()


def _required(reason: str | None) -> str:
    if reason is None or not reason.strip():
        raise ReasonRequired
    return reason.strip()


def _optional(reason: str | None) -> str | None:
    return None if reason is None or not reason.strip() else reason.strip()


def _list_prices(session: Session, codes: set[str]) -> dict[str, Decimal] | None:
    """List prices of the products; None when one of them is gone from the catalogue."""
    prices: dict[str, Decimal] = {
        product.code: product.list_price
        for product in session.exec(select(Product).where(col(Product.code).in_(codes))).all()
    }
    return prices if codes <= prices.keys() else None


def _locked_draft(
    session: Session, inquiry_id: int, updated_at: datetime
) -> tuple[InquiryAnalysis, InquiryDraft, DraftResult, RecommendationResult]:
    """The draft read at `updated_at`, in status `draft` and of the current recommendation,
    with the analysis locked until the session commits."""
    analysis = lock_analysis(session, inquiry_id)
    if analysis is None:
        raise NothingToDraft
    row = session.exec(
        select(InquiryDraft).where(col(InquiryDraft.inquiry_id) == inquiry_id)
    ).first()
    if row is None:
        raise NothingToDraft
    if row.updated_at != updated_at:
        raise DraftChanged
    if row.status != "draft":
        raise DraftNotEditable
    recommendation = _recommendation(session, inquiry_id)
    if (
        recommendation is None
        or recommendation.status != "completed"
        or recommendation.recommended_at != row.recommended_at
        or not is_current(session, recommendation, analysis)
    ):
        raise DraftStale
    try:
        result = DraftResult.model_validate(row.result)
        recommended = RecommendationResult.model_validate(recommendation.result)
    except ValidationError as error:
        # Hidden in the view as well; class and inquiry id only.
        logger.error(
            "Stored draft or recommendation of inquiry %s does not match the schema: %s",
            inquiry_id,
            type(error).__name__,
        )
        raise DraftStale from None
    return analysis, row, result, recommended


def _policy_in_force(
    session: Session, row: InquiryDraft, result: DraftResult
) -> PolicyResult | None:
    """The edit's own verdict for an edited offer; else the policy stage's verdict of the
    draft's recommendation (None when missing, of another recommendation or not readable).

    The caller already checked that the draft's recommendation is the current one.
    """
    if result.offer.edited:
        return result.policy
    verdict = session.exec(
        select(InquiryPolicyVerdict).where(col(InquiryPolicyVerdict.inquiry_id) == row.inquiry_id)
    ).first()
    if verdict is None or verdict.recommended_at != row.recommended_at:
        return None
    try:
        return PolicyResult.model_validate(verdict.result)
    except ValidationError as error:
        logger.error(
            "Stored policy verdict of inquiry %s does not match the schema: %s",
            row.inquiry_id,
            type(error).__name__,
        )
        return None


def _decide(
    session: Session,
    row: InquiryDraft,
    user: AuthUser,
    action: DecisionAction,
    status_after: DraftStatus,
    reason: str | None,
    offer: DraftOffer,
    policy: PolicyResult | None,
) -> None:
    """Set the draft's new status and token and append the decision, in one commit."""
    now = datetime.now(UTC)
    rules = [] if policy is None else policy.rules
    snapshot = DecisionSnapshot(
        offer=offer,
        policy_outcome=None if policy is None else policy.outcome,
        failing_rules=[rule.code for rule in rules if rule.verdict == "fail"],
    )
    row.status = status_after
    row.updated_at = now
    session.add(row)
    session.add(
        InquiryDraftDecision(
            inquiry_id=row.inquiry_id,
            recommended_at=row.recommended_at,
            action=action,
            status_after=status_after,
            reason=reason,
            decided_by=user.id,
            decided_at=now,
            snapshot=snapshot.model_dump(mode="json"),
        )
    )
    session.commit()


def _user_name(session: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = session.get(User, user_id)
    return None if user is None else user.display_name
