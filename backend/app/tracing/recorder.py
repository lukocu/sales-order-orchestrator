"""Context managers that time runs and steps and persist them, also when the body raises.

Durations come only from `time.perf_counter_ns()`; `started_at` is wall-clock UTC for ordering.
The run and every step write through their own short session and commit at once, so finished
steps survive a run that fails later.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlmodel import Session

from app.tracing.models import RunStatus, StepKind, StepStatus, TraceRun, TraceStep
from app.tracing.pricing import LlmUsage, PriceResult, price_usage


def _elapsed_us(start_ns: int) -> int:
    return (time.perf_counter_ns() - start_ns) // 1000


class StepRecorder:
    """Collects what a step reports about itself; written when the step exits."""

    def __init__(self, kind: StepKind) -> None:
        self.kind: StepKind = kind
        self.usage: LlmUsage | None = None
        self.price: PriceResult | None = None

    def record_usage(self, usage: LlmUsage) -> None:
        """Record and price the step's single model call (priced per call, not per token sum)."""
        if self.kind != "llm":
            raise ValueError(f"record_usage is only allowed in llm steps, not {self.kind!r}")
        if self.usage is not None:
            raise ValueError("record_usage was already called for this step")
        price = price_usage(usage)
        self.usage = usage
        self.price = price

    def _to_row(
        self,
        *,
        run_id: int,
        name: str,
        status: StepStatus,
        error_type: str | None,
        started_at: datetime,
        duration_us: int,
    ) -> TraceStep:
        step = TraceStep(
            run_id=run_id,
            name=name,
            kind=self.kind,
            status=status,
            error_type=error_type,
            price_status="not_applicable" if self.kind == "deterministic" else "unpriced",
            started_at=started_at,
            duration_us=duration_us,
        )
        if self.usage is not None and self.price is not None:
            step.provider = self.usage.provider
            step.model = self.usage.model
            step.input_tokens = self.usage.input_tokens
            step.output_tokens = self.usage.output_tokens
            step.cache_read_tokens = self.usage.cache_read_tokens
            step.cache_write_tokens = self.usage.cache_write_tokens
            step.raw_usage = self.usage.raw
            step.cost_usd = self.price.cost_usd
            step.price_status = self.price.status
            step.price_source = self.price.source
        return step


class RunHandle:
    """An open run; steps are opened from it."""

    def __init__(self, engine: Engine, run_id: int) -> None:
        self._engine = engine
        self.id = run_id

    @contextmanager
    def step(self, name: str, *, kind: StepKind) -> Iterator[StepRecorder]:
        recorder = StepRecorder(kind)
        started_at = datetime.now(UTC)
        start_ns = time.perf_counter_ns()
        status: StepStatus = "ok"
        error_type: str | None = None
        try:
            yield recorder
        except BaseException as exc:
            status = "failed"
            error_type = type(exc).__name__
            raise
        finally:
            row = recorder._to_row(
                run_id=self.id,
                name=name,
                status=status,
                error_type=error_type,
                started_at=started_at,
                duration_us=_elapsed_us(start_ns),
            )
            with Session(self._engine) as session:
                session.add(row)
                session.commit()


@contextmanager
def run(engine: Engine, *, subject_type: str, subject_id: str) -> Iterator[RunHandle]:
    """Open a traced run: inserted as `running`, finished as `completed` or `failed`."""
    trace_run = TraceRun(
        subject_type=subject_type,
        subject_id=subject_id,
        status="running",
        started_at=datetime.now(UTC),
    )
    with Session(engine) as session:
        session.add(trace_run)
        session.commit()
        session.refresh(trace_run)
    assert trace_run.id is not None
    run_id = trace_run.id
    start_ns = time.perf_counter_ns()
    status: RunStatus = "completed"
    try:
        yield RunHandle(engine, run_id)
    except BaseException:
        status = "failed"
        raise
    finally:
        duration_us = _elapsed_us(start_ns)
        with Session(engine) as session:
            row = session.get_one(TraceRun, run_id)
            row.status = status
            row.duration_us = duration_us
            session.add(row)
            session.commit()
