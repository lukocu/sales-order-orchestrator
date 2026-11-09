import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.db import get_engine
from app.tracing.summary import RunSummary, get_run_summary

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/runs/{run_id}", response_model=RunSummary)
def read_run(
    # trace_runs.id is a Postgres int4; out-of-range ids are a 422, not a driver error.
    run_id: Annotated[int, Path(ge=1, le=2_147_483_647)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> RunSummary:
    """A traced run with step metrics and totals; never prompts or `raw_usage`."""
    try:
        with Session(engine) as session:
            summary = get_run_summary(session, run_id)
    except SQLAlchemyError:
        logger.exception("Runs API: database unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from None
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return summary
