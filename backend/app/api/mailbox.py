import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.api.errors import database_unavailable
from app.db import get_engine
from app.mailbox.client import (
    Mailbox,
    MailboxAuthFailed,
    MailboxError,
    MailboxNotConfigured,
    MailboxUnavailable,
    get_mailbox,
)
from app.mailbox.service import FetchResult, MailboxBusy, fetch_mailbox

logger = logging.getLogger(__name__)

router = APIRouter()


def _mailbox_failed(error: MailboxError) -> HTTPException:
    # Class only: the details of a mailbox failure belong to the server, not to the log.
    logger.warning("Mailbox API: fetch failed: %s", type(error).__name__)
    if isinstance(error, MailboxNotConfigured):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Mailbox not configured"
        )
    if isinstance(error, MailboxAuthFailed):
        detail = "Mailbox login failed"
    elif isinstance(error, MailboxUnavailable):
        detail = "Mailbox unavailable"
    else:
        detail = "Mailbox error"
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


@router.post("/mailbox/fetch", response_model=FetchResult)
def fetch_mail(
    engine: Annotated[Engine, Depends(get_engine)],
    mailbox: Annotated[Mailbox, Depends(get_mailbox)],
) -> FetchResult:
    """Store the newest messages of the test mailbox that are not inquiries yet."""
    try:
        return fetch_mailbox(engine, mailbox)
    except MailboxBusy:
        logger.info("Mailbox API: fetch refused: MailboxBusy")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Mailbox fetch already in progress"
        ) from None
    except MailboxError as error:
        raise _mailbox_failed(error) from None
    except SQLAlchemyError as error:
        # Class only: a database error could quote message content.
        logger.error("Mailbox API: database unavailable: %s", type(error).__name__)
        raise database_unavailable() from None
