"""Supervisor-only reads for the approval queue and review screen."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.api.errors import database_unavailable
from app.auth.deps import AuthUser, require_supervisor
from app.db import get_engine
from app.inquiries.supervisor_queue import QueueView, ReviewView, get_queue, get_review

logger = logging.getLogger(__name__)
router = APIRouter()
InquiryId = Annotated[int, Path(ge=1, le=2_147_483_647)]


@router.get("/supervisor/queue", response_model=QueueView)
def read_queue(
    engine: Annotated[Engine, Depends(get_engine)],
    _user: Annotated[AuthUser, Depends(require_supervisor)],
) -> QueueView:
    try:
        with Session(engine) as session:
            return get_queue(session)
    except SQLAlchemyError:
        logger.exception("Supervisor API: database unavailable")
        raise database_unavailable() from None


@router.get("/supervisor/reviews/{inquiry_id}", response_model=ReviewView)
def read_review(
    inquiry_id: InquiryId,
    engine: Annotated[Engine, Depends(get_engine)],
    user: Annotated[AuthUser, Depends(require_supervisor)],
) -> ReviewView:
    try:
        with Session(engine) as session:
            review = get_review(session, inquiry_id, user.id)
    except SQLAlchemyError:
        logger.exception("Supervisor API: database unavailable")
        raise database_unavailable() from None
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found")
    return review
