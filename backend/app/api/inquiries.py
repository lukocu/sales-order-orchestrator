import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.auth.deps import database_unavailable
from app.db import get_engine
from app.inquiries.models import Inquiry

logger = logging.getLogger(__name__)

router = APIRouter()


class InquirySummary(BaseModel):
    id: int
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime


class InquiryDetail(InquirySummary):
    body: str


@router.get("/inquiries", response_model=list[InquirySummary])
def list_inquiries(engine: Annotated[Engine, Depends(get_engine)]) -> list[InquirySummary]:
    """All inquiries, newest first."""
    statement = select(Inquiry).order_by(col(Inquiry.received_at).desc(), col(Inquiry.id).desc())
    try:
        with Session(engine) as session:
            inquiries = session.exec(statement).all()
            return [InquirySummary.model_validate(i, from_attributes=True) for i in inquiries]
    except SQLAlchemyError:
        logger.exception("Inquiries API: database unavailable")
        raise database_unavailable() from None


@router.get("/inquiries/{inquiry_id}", response_model=InquiryDetail)
def read_inquiry(
    # inquiries.id is a Postgres int4; out-of-range ids are a 422, not a driver error.
    inquiry_id: Annotated[int, Path(ge=1, le=2_147_483_647)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> InquiryDetail:
    try:
        with Session(engine) as session:
            inquiry = session.get(Inquiry, inquiry_id)
            detail = (
                InquiryDetail.model_validate(inquiry, from_attributes=True)
                if inquiry is not None
                else None
            )
    except SQLAlchemyError:
        logger.exception("Inquiries API: database unavailable")
        raise database_unavailable() from None
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found")
    return detail
