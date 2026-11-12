"""Run, store, read and correct the analysis of an inquiry (independent of FastAPI).

No database connection is held while the extractor runs: the inquiry is read in one short
session, the extraction runs inside a tracing run, and the result is written in another
short session. After every stored analysis or correction the checks run in their own run
(`app.checks.service`), after a stored check result the orchestration runs in another
(`app.orchestration.service`), after it the recommendation in a third
(`app.recommendation.service`), after that the policy in a fourth (`app.policy.service`)
and the reply draft in a fifth (`app.draft.service`); their failure never undoes the stored
analysis.
"""

import logging
from datetime import UTC, date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.checks.service import ChecksView, NoAnalysis, get_checks_view, run_checks
from app.draft.drafter import Drafter
from app.draft.offer import LineEdit
from app.draft.service import (
    DecisionView,
    DraftView,
    decide,
    draft_after_policy,
    edit_draft,
    get_decision_views,
    get_draft_view,
    regenerate_draft,
)
from app.inquiries.models import Inquiry
from app.orchestration.planning import Planner
from app.orchestration.service import (
    OrchestrationView,
    get_orchestration_view,
    orchestrate_after_checks,
    run_orchestration,
)
from app.parsing.analyze import build_parsed
from app.parsing.extractor import ExtractionError, ExtractionResult, InquiryExtractor
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import FieldName, ParsedFields
from app.policy.service import (
    PolicyView,
    get_policy_view,
    policy_after_recommendation,
    run_policy,
)
from app.recommendation.recommender import Recommender
from app.recommendation.service import (
    RecommendationView,
    get_recommendation_view,
    recommend_after_orchestration,
    run_recommendation,
)
from app.settings import LlmProvider
from app.tracing import run
from app.tracing.summary import RunSummary, get_run_summary

logger = logging.getLogger(__name__)

REFERENCE_TIMEZONE = ZoneInfo("Europe/Warsaw")
SUBJECT_TYPE = "inquiry"

# Which ParsedFields attributes make up each field the user sees and corrects.
FIELD_ATTRIBUTES: dict[FieldName, tuple[str, ...]] = {
    "customer": ("customer",),
    "product_code": ("product_code",),
    "quantity": ("quantity",),
    "deadline": ("deadline", "deadline_text"),
    "substitute_allowed": ("substitute_allowed",),
    "price": ("price_kind", "price_value", "price_text"),
}


class InquiryNotFound(Exception):
    pass


class AnalysisNotFound(Exception):
    """The inquiry has no analysis yet."""


class AnalysisChanged(Exception):
    """The analysis was replaced after the version being corrected was read."""


class AnalysisView(BaseModel):
    # `model_fields` is a pydantic name: the attribute is renamed, the JSON key is not.
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    inquiry_id: int
    extractor: LlmProvider
    reference_date: date
    fields: ParsedFields
    fields_from_model: ParsedFields = Field(alias="model_fields")
    uncertain: dict[FieldName, str]
    corrected_fields: list[FieldName]  # fields whose value differs from the model's
    analyzed_at: datetime
    analyzed_by_name: str | None
    corrected_at: datetime | None
    corrected_by_name: str | None
    run: RunSummary | None  # None when the run could not be traced or was deleted
    checks: ChecksView | None  # None until checks succeeded once; has its own run
    # None until an exception was orchestrated, and again once the checks find none
    orchestration: OrchestrationView | None
    # None until an orchestration could be recommended from, and again once it is gone
    recommendation: RecommendationView | None
    # None until a recommendation with a chosen option was evaluated, and again once it is gone
    policy: PolicyView | None
    # None until a recommendation with a chosen option was drafted, and again once it is gone
    draft: DraftView | None
    # every decision on the inquiry's drafts, oldest first, also of earlier recommendations
    decisions: list[DecisionView]


def reference_date_of(received_at: datetime) -> date:
    """The day the inquiry arrived, as seen in Poland."""
    return received_at.astimezone(REFERENCE_TIMEZONE).date()


def changed_fields(before: ParsedFields, after: ParsedFields) -> list[FieldName]:
    return [
        field
        for field, attributes in FIELD_ATTRIBUTES.items()
        if any(getattr(before, name) != getattr(after, name) for name in attributes)
    ]


def analyze_inquiry(
    engine: Engine,
    extractor: InquiryExtractor,
    inquiry_id: int,
    user: AuthUser,
    planner: Planner,
    recommender: Recommender,
    drafter: Drafter,
) -> AnalysisView:
    """Analyze the inquiry and replace its current analysis (corrections are dropped).

    Extraction errors propagate and leave the stored analysis unchanged.
    """
    with Session(engine) as session:
        inquiry = session.get(Inquiry, inquiry_id)
        if inquiry is None:
            raise InquiryNotFound
        subject, body = inquiry.subject, inquiry.body
        reference_date = reference_date_of(inquiry.received_at)

    with run(engine, subject_type=SUBJECT_TYPE, subject_id=str(inquiry_id)) as traced:
        with traced.step("parse", kind=extractor.step_kind) as step:
            try:
                result: ExtractionResult = extractor.extract(subject, body, reference_date)
            except ExtractionError as error:
                # The provider may have billed the call before it failed.
                if error.usage is not None:
                    step.record_usage(error.usage)
                raise
            if result.usage is not None:
                step.record_usage(result.usage)
        with traced.step("resolve-deadline", kind="deterministic"):
            fields, uncertain = build_parsed(result.extraction, reference_date)

    stored_fields = fields.model_dump(mode="json")
    values: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "run_id": traced.id,
        "extractor": extractor.name,
        "reference_date": reference_date,
        "model_fields": stored_fields,
        "fields": stored_fields,
        "uncertain": dict(uncertain),
        "analyzed_at": datetime.now(UTC),
        "analyzed_by": user.id,
        "corrected_at": None,
        "corrected_by": None,
    }
    # The core table, so `values` use column names (`model_fields`, not the attribute).
    table = InquiryAnalysis.metadata.tables[InquiryAnalysis.__tablename__]
    statement = insert(table).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["inquiry_id"],
        set_={name: statement.excluded[name] for name in values if name != "inquiry_id"},
    )
    with Session(engine) as session:
        session.exec(statement)
        session.commit()
    _run_checks_after_save(engine, inquiry_id, planner, recommender, drafter)
    return _current_view(engine, inquiry_id)


def get_analysis(engine: Engine, inquiry_id: int) -> AnalysisView | None:
    """The current analysis; None when there is none yet. Raises `InquiryNotFound`."""
    with Session(engine) as session:
        analysis = _find(session, inquiry_id)
        if analysis is not None:
            return _view(session, analysis)
        if session.get(Inquiry, inquiry_id) is None:
            raise InquiryNotFound
        return None


def save_corrections(
    engine: Engine,
    inquiry_id: int,
    fields: ParsedFields,
    reviewed: list[FieldName],
    analyzed_at: datetime,
    user: AuthUser,
    planner: Planner,
    recommender: Recommender,
    drafter: Drafter,
) -> AnalysisView:
    """Store the user's values for the analysis read at `analyzed_at`.

    Fields the user changed or marked as reviewed are no longer uncertain. Raises
    `AnalysisNotFound` without an analysis and `AnalysisChanged` (nothing saved) when the
    analysis was replaced since `analyzed_at`.
    """
    with Session(engine) as session:
        # Locked, so a concurrent re-analysis cannot slip in between check and write.
        analysis = _find(session, inquiry_id, for_update=True)
        if analysis is None:
            raise AnalysisNotFound
        if analysis.analyzed_at != analyzed_at:
            raise AnalysisChanged
        previous = ParsedFields.model_validate(analysis.fields)
        cleared = set(changed_fields(previous, fields)) | set(reviewed)
        analysis.fields = fields.model_dump(mode="json")
        analysis.uncertain = {
            field: reason for field, reason in analysis.uncertain.items() if field not in cleared
        }
        analysis.corrected_at = datetime.now(UTC)
        analysis.corrected_by = user.id
        session.add(analysis)
        session.commit()
    # Outside the lock: the checks lock the analysis again only to store their result.
    _run_checks_after_save(engine, inquiry_id, planner, recommender, drafter)
    return _current_view(engine, inquiry_id)


def recheck_inquiry(
    engine: Engine,
    inquiry_id: int,
    planner: Planner,
    recommender: Recommender,
    drafter: Drafter,
) -> AnalysisView:
    """Run the checks again in a new run for the current analysis, then the orchestration
    and the recommendation.

    Raises `InquiryNotFound`, `NoAnalysis` without an analysis, and whatever the checks raise.
    A failing orchestration or recommendation is only logged.
    """
    try:
        run_checks(engine, inquiry_id)
    except NoAnalysis:
        with Session(engine) as session:
            if session.get(Inquiry, inquiry_id) is None:
                raise InquiryNotFound from None
        raise
    orchestrate_after_checks(engine, inquiry_id, planner, recommender, drafter)
    return _current_view(engine, inquiry_id)


def reorchestrate_inquiry(
    engine: Engine,
    inquiry_id: int,
    planner: Planner,
    recommender: Recommender,
    drafter: Drafter,
) -> AnalysisView:
    """Run the orchestration again in a new run for the current analysis, then the
    recommendation (a single recommender attempt; its failure is only logged).

    Raises `InquiryNotFound`, `AnalysisNotFound` without an analysis, `NothingToOrchestrate`
    when its current check result is not an exception, and unexpected orchestration errors.
    """
    with Session(engine) as session:
        if _find(session, inquiry_id) is None:
            if session.get(Inquiry, inquiry_id) is None:
                raise InquiryNotFound
            raise AnalysisNotFound
    run_orchestration(engine, inquiry_id, planner)
    recommend_after_orchestration(engine, inquiry_id, recommender, drafter)
    return _current_view(engine, inquiry_id)


def rerecommend_inquiry(
    engine: Engine, inquiry_id: int, recommender: Recommender, drafter: Drafter
) -> AnalysisView:
    """Run only the recommendation again in a new run for the current orchestration, then
    the policy and the draft (also when the recommendation raised, so an outdated verdict and
    draft are dropped; their failure is only logged).

    Raises `InquiryNotFound`, `AnalysisNotFound` without an analysis, `NothingToRecommend`
    without a current exception with a `completed` or `partial` orchestration, and unexpected
    recommendation errors.
    """
    with Session(engine) as session:
        if _find(session, inquiry_id) is None:
            if session.get(Inquiry, inquiry_id) is None:
                raise InquiryNotFound
            raise AnalysisNotFound
    try:
        run_recommendation(engine, inquiry_id, recommender)
    finally:
        policy_after_recommendation(engine, inquiry_id)
        draft_after_policy(engine, inquiry_id, drafter)
    return _current_view(engine, inquiry_id)


def reevaluate_policy_inquiry(engine: Engine, inquiry_id: int, drafter: Drafter) -> AnalysisView:
    """Evaluate only the policy again in a new run for the current recommendation, then
    follow with the draft: an existing draft of the current recommendation is kept, a
    missing one is drafted, a draft of old data is dropped (only logged on failure).

    Raises `InquiryNotFound`, `AnalysisNotFound` without an analysis, `NothingToEvaluate`
    without a current recommendation with a chosen option, and unexpected policy errors.
    """
    with Session(engine) as session:
        if _find(session, inquiry_id) is None:
            if session.get(Inquiry, inquiry_id) is None:
                raise InquiryNotFound
            raise AnalysisNotFound
    try:
        run_policy(engine, inquiry_id)
    finally:
        draft_after_policy(engine, inquiry_id, drafter)
    return _current_view(engine, inquiry_id)


def redraft_inquiry(engine: Engine, inquiry_id: int, drafter: Drafter) -> AnalysisView:
    """Draft the current recommendation again ("Regenerate draft"), resetting the offer.

    Raises `InquiryNotFound`, `AnalysisNotFound` without an analysis, `NothingToDraft`
    without a current recommendation with a chosen option, `DraftDecided` for an approved
    draft of the current recommendation, and unexpected drafting errors.
    """
    with Session(engine) as session:
        if _find(session, inquiry_id) is None:
            if session.get(Inquiry, inquiry_id) is None:
                raise InquiryNotFound
            raise AnalysisNotFound
    regenerate_draft(engine, inquiry_id, drafter)
    return _current_view(engine, inquiry_id)


def edit_draft_inquiry(
    engine: Engine,
    inquiry_id: int,
    user: AuthUser,
    *,
    updated_at: datetime,
    option_id: str,
    lines: list[LineEdit],
    reason: str | None,
) -> AnalysisView:
    """Edit the draft's offer (see `app.draft.service.edit_draft`).

    Raises `InquiryNotFound`, `AnalysisNotFound` without an analysis and whatever
    `edit_draft` raises.
    """
    _require_analysis(engine, inquiry_id)
    edit_draft(
        engine,
        inquiry_id,
        user,
        updated_at=updated_at,
        option_id=option_id,
        lines=lines,
        reason=reason,
    )
    return _current_view(engine, inquiry_id)


def decide_draft_inquiry(
    engine: Engine,
    inquiry_id: int,
    user: AuthUser,
    *,
    updated_at: datetime,
    action: Literal["approve", "reject"],
    reason: str | None,
) -> AnalysisView:
    """Approve or reject the draft (see `app.draft.service.decide`).

    Raises `InquiryNotFound`, `AnalysisNotFound` without an analysis and whatever `decide`
    raises.
    """
    _require_analysis(engine, inquiry_id)
    decide(engine, inquiry_id, user, updated_at=updated_at, action=action, reason=reason)
    return _current_view(engine, inquiry_id)


def _require_analysis(engine: Engine, inquiry_id: int) -> None:
    with Session(engine) as session:
        if _find(session, inquiry_id) is None:
            if session.get(Inquiry, inquiry_id) is None:
                raise InquiryNotFound
            raise AnalysisNotFound


def _run_checks_after_save(
    engine: Engine,
    inquiry_id: int,
    planner: Planner,
    recommender: Recommender,
    drafter: Drafter,
) -> None:
    """Checks, then the orchestration and the recommendation, after a saved analysis or
    correction.

    A failure leaves the result stale or empty and is only logged.
    """
    try:
        run_checks(engine, inquiry_id)
    except Exception as error:
        # Class and inquiry id only: the message could quote inquiry content.
        logger.warning("Checks failed for inquiry %s: %s", inquiry_id, type(error).__name__)
        return
    orchestrate_after_checks(engine, inquiry_id, planner, recommender, drafter)


def _current_view(engine: Engine, inquiry_id: int) -> AnalysisView:
    with Session(engine) as session:
        analysis = _find(session, inquiry_id)
        if analysis is None:  # the inquiry was deleted meanwhile
            raise InquiryNotFound
        return _view(session, analysis)


def _find(session: Session, inquiry_id: int, *, for_update: bool = False) -> InquiryAnalysis | None:
    statement = select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
    if for_update:
        statement = statement.with_for_update()
    return session.exec(statement).first()


def _user_name(session: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = session.get(User, user_id)
    return None if user is None else user.display_name


def _view(session: Session, analysis: InquiryAnalysis) -> AnalysisView:
    fields = ParsedFields.model_validate(analysis.fields)
    fields_from_model = ParsedFields.model_validate(analysis.fields_from_model)
    recommendation = get_recommendation_view(session, analysis)
    policy = get_policy_view(session, analysis)
    if policy is not None and recommendation is not None and recommendation.stale:
        policy.stale = True  # evaluated from a recommendation of data that changed since
    return AnalysisView(
        inquiry_id=analysis.inquiry_id,
        extractor=analysis.extractor,
        reference_date=analysis.reference_date,
        fields=fields,
        fields_from_model=fields_from_model,
        uncertain=analysis.uncertain,
        corrected_fields=changed_fields(fields_from_model, fields),
        analyzed_at=analysis.analyzed_at,
        analyzed_by_name=_user_name(session, analysis.analyzed_by),
        corrected_at=analysis.corrected_at,
        corrected_by_name=_user_name(session, analysis.corrected_by),
        run=None if analysis.run_id is None else get_run_summary(session, analysis.run_id),
        checks=get_checks_view(session, analysis),
        orchestration=get_orchestration_view(session, analysis),
        recommendation=recommendation,
        policy=policy,
        draft=get_draft_view(session, analysis),
        decisions=get_decision_views(session, analysis),
    )
