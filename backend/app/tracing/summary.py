"""Read side of tracing: one run with its steps and totals, metrics only.

The single read used by `GET /api/runs/{run_id}` and later by inquiry and eval views.
`raw_usage` is never exposed. `Decimal` values serialize to JSON strings, so no precision
is lost.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.tracing.models import PriceStatus, RunStatus, StepKind, StepStatus, TraceRun, TraceStep


def _us_to_ms(duration_us: int) -> float:
    return duration_us / 1000


class StepSummary(BaseModel):
    id: int
    name: str
    kind: StepKind
    status: StepStatus
    error_type: str | None
    provider: str | None
    model: str | None
    input_tokens: int  # includes cache_read_tokens and cache_write_tokens
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: Decimal | None
    price_status: PriceStatus
    price_source: str | None
    started_at: datetime
    duration_ms: float


class RunTotals(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: Decimal  # sum over `priced` steps only
    cost_complete: bool  # false when any step is `unpriced`
    steps_duration_ms: float
    duration_ms: float | None  # the run's own duration; None while it is running


class RunSummary(BaseModel):
    id: int
    subject_type: str
    subject_id: str
    status: RunStatus
    started_at: datetime
    duration_ms: float | None
    steps: list[StepSummary]
    totals: RunTotals


def _step_summary(step: TraceStep) -> StepSummary:
    assert step.id is not None
    return StepSummary(
        id=step.id,
        name=step.name,
        kind=step.kind,
        status=step.status,
        error_type=step.error_type,
        provider=step.provider,
        model=step.model,
        input_tokens=step.input_tokens,
        output_tokens=step.output_tokens,
        cache_read_tokens=step.cache_read_tokens,
        cache_write_tokens=step.cache_write_tokens,
        cost_usd=step.cost_usd,
        price_status=step.price_status,
        price_source=step.price_source,
        started_at=step.started_at,
        duration_ms=_us_to_ms(step.duration_us),
    )


def get_run_summary(session: Session, run_id: int) -> RunSummary | None:
    """The run with its steps (by `started_at`, then `id`) and totals; None if it does not exist."""
    trace_run = session.get(TraceRun, run_id)
    if trace_run is None:
        return None
    assert trace_run.id is not None
    statement = (
        select(TraceStep)
        .where(TraceStep.run_id == run_id)
        .order_by(col(TraceStep.started_at), col(TraceStep.id))
    )
    steps = list(session.exec(statement).all())
    duration_ms = None if trace_run.duration_us is None else _us_to_ms(trace_run.duration_us)
    totals = RunTotals(
        input_tokens=sum(step.input_tokens for step in steps),
        output_tokens=sum(step.output_tokens for step in steps),
        cache_read_tokens=sum(step.cache_read_tokens for step in steps),
        cost_usd=sum(
            (
                step.cost_usd
                for step in steps
                if step.price_status == "priced" and step.cost_usd is not None
            ),
            Decimal(0),
        ),
        cost_complete=all(step.price_status != "unpriced" for step in steps),
        steps_duration_ms=_us_to_ms(sum(step.duration_us for step in steps)),
        duration_ms=duration_ms,
    )
    return RunSummary(
        id=trace_run.id,
        subject_type=trace_run.subject_type,
        subject_id=trace_run.subject_id,
        status=trace_run.status,
        started_at=trace_run.started_at,
        duration_ms=duration_ms,
        steps=[_step_summary(step) for step in steps],
        totals=totals,
    )
