"""Run, store, read and correct the analysis of an inquiry (independent of FastAPI).

No database connection is held while the extractor runs: the inquiry is read in one short
session, the extraction runs inside a tracing run, and the result is written in another
short session.
"""

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.inquiries.models import Inquiry
from app.parsing.analyze import build_parsed
from app.parsing.extractor import ExtractionError, ExtractionResult, InquiryExtractor
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import FieldName, ParsedFields
from app.settings import LlmProvider
from app.tracing import run
from app.tracing.summary import RunSummary, get_run_summary

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
    engine: Engine, extractor: InquiryExtractor, inquiry_id: int, user: AuthUser
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
        analysis = _find(session, inquiry_id)
        assert analysis is not None
        return _view(session, analysis)


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
        session.refresh(analysis)
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
    )
