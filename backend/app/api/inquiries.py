import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.api.errors import database_unavailable
from app.checks.schema import Outcome
from app.checks.service import current_outcome, with_current_outcome
from app.db import get_engine
from app.draft.models import InquiryDraft
from app.draft.schema import DraftStatus
from app.inquiries.models import Inquiry

logger = logging.getLogger(__name__)

router = APIRouter()


class InquirySummary(BaseModel):
    id: int
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    outcome: Outcome | None = None  # of the check result, only while it is current
    # Raw status of the stored draft (also when it is stale); None without a draft.
    draft_status: DraftStatus | None = None


class InquiryDetail(InquirySummary):
    body: str


def _with_outcome[T: InquirySummary](
    model: type[T], inquiry: Inquiry, outcome: Any, draft_status: Any
) -> T:
    summary = model.model_validate(inquiry, from_attributes=True)
    return summary.model_copy(update={"outcome": outcome, "draft_status": draft_status})


def _inquiry_rows() -> Any:
    """`(Inquiry, outcome, draft status)` rows, one per inquiry (a draft is unique per
    inquiry)."""
    return with_current_outcome(select(Inquiry, current_outcome(), InquiryDraft.status)).outerjoin(
        InquiryDraft, col(InquiryDraft.inquiry_id) == col(Inquiry.id)
    )


@router.get("/inquiries", response_model=list[InquirySummary])
def list_inquiries(engine: Annotated[Engine, Depends(get_engine)]) -> list[InquirySummary]:
    """All inquiries, newest first."""
    statement = _inquiry_rows().order_by(col(Inquiry.received_at).desc(), col(Inquiry.id).desc())
    try:
        with Session(engine) as session:
            rows = session.exec(statement).all()
            return [
                _with_outcome(InquirySummary, inquiry, outcome, draft_status)
                for inquiry, outcome, draft_status in rows
            ]
    except SQLAlchemyError:
        logger.exception("Inquiries API: database unavailable")
        raise database_unavailable() from None


@router.get("/inquiries/{inquiry_id}", response_model=InquiryDetail)
def read_inquiry(
    # inquiries.id is a Postgres int4; out-of-range ids are a 422, not a driver error.
    inquiry_id: Annotated[int, Path(ge=1, le=2_147_483_647)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> InquiryDetail:
    statement = _inquiry_rows().where(col(Inquiry.id) == inquiry_id)
    try:
        with Session(engine) as session:
            row = session.exec(statement).first()
            detail = None if row is None else _with_outcome(InquiryDetail, *row)
    except SQLAlchemyError:
        logger.exception("Inquiries API: database unavailable")
        raise database_unavailable() from None
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found")
    return detail
