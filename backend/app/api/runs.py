from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Engine
from sqlmodel import Session

from app.db import get_engine
from app.tracing.summary import RunSummary, get_run_summary

router = APIRouter()


@router.get("/runs/{run_id}", response_model=RunSummary)
def read_run(run_id: int, engine: Annotated[Engine, Depends(get_engine)]) -> RunSummary:
    """A traced run with step metrics and totals; never prompts or `raw_usage`."""
    with Session(engine) as session:
        summary = get_run_summary(session, run_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return summary
