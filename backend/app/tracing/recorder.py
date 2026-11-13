"""Context managers that time runs and steps and persist them, also when the body raises.

Durations come only from `time.perf_counter_ns()`. The wall clock is read once per run, when it
opens; a step's `started_at` is that reading plus the monotonic time elapsed since. The wall clock
can step backwards (an NTP or VM clock resync), and reading it per step could then order a later
step before an earlier one; the monotonic offset keeps `started_at` in execution order.
The run and every step write through their own short session and commit at once, so finished
steps survive a run that fails later.

Tracing never breaks the work it wraps: a failed trace write (database down, a value too long
for its column) is logged and dropped, and the body's own result or exception always wins.
When the run itself cannot be opened, `RunHandle.id` is None and its steps are not written.

Writes are synchronous; from `async def` code they block the event loop, so call them from a
worker thread there. An interrupt or cancellation inside a run or step is recorded as `failed`.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.tracing.models import RunStatus, StepKind, StepStatus, TraceRun, TraceStep
from app.tracing.pricing import LlmUsage, PriceResult, price_usage

logger = logging.getLogger(__name__)


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
    """An open run; steps are opened from it. `id` is None when the run could not be saved."""

    def __init__(
        self, engine: Engine, run_id: int | None, started_at: datetime, start_ns: int
    ) -> None:
        self._engine = engine
        self.id = run_id
        self._started_at = started_at  # the run's single wall-clock reading
        self._start_ns = start_ns  # the monotonic reading taken with it

    def _now(self) -> datetime:
        """Wall-clock time derived from the monotonic clock, so it never goes backwards in a run."""
        return self._started_at + timedelta(microseconds=_elapsed_us(self._start_ns))

    @contextmanager
    def step(self, name: str, *, kind: StepKind) -> Iterator[StepRecorder]:
        recorder = StepRecorder(kind)
        start_ns = time.perf_counter_ns()
        started_at = self._now()
        status: StepStatus = "ok"
        error_type: str | None = None
        try:
            yield recorder
        except BaseException as exc:
            status = "failed"
            error_type = type(exc).__name__
            raise
        finally:
            if self.id is not None:
                row = recorder._to_row(
                    run_id=self.id,
                    name=name,
                    status=status,
                    error_type=error_type,
                    started_at=started_at,
                    duration_us=_elapsed_us(start_ns),
                )
                try:
                    with Session(self._engine) as session:
                        session.add(row)
                        session.commit()
                except SQLAlchemyError:
                    logger.exception("Tracing: could not save step %r of run %s", name, self.id)


def _open_run(
    engine: Engine, subject_type: str, subject_id: str, started_at: datetime
) -> int | None:
    trace_run = TraceRun(
        subject_type=subject_type,
        subject_id=subject_id,
        status="running",
        started_at=started_at,
    )
    try:
        with Session(engine) as session:
            session.add(trace_run)
            session.commit()
            session.refresh(trace_run)
    except SQLAlchemyError:
        logger.exception("Tracing: could not open run for %s/%s", subject_type, subject_id)
        return None
    return trace_run.id


def _finish_run(engine: Engine, run_id: int, status: RunStatus, duration_us: int) -> None:
    try:
        with Session(engine) as session:
            row = session.get_one(TraceRun, run_id)
            row.status = status
            row.duration_us = duration_us
            session.add(row)
            session.commit()
    except SQLAlchemyError:
        logger.exception("Tracing: could not finish run %s", run_id)


@contextmanager
def run(engine: Engine, *, subject_type: str, subject_id: str) -> Iterator[RunHandle]:
    """Open a traced run: inserted as `running`, finished as `completed` or `failed`."""
    started_at = datetime.now(UTC)
    start_ns = time.perf_counter_ns()
    run_id = _open_run(engine, subject_type, subject_id, started_at)
    status: RunStatus = "completed"
    try:
        yield RunHandle(engine, run_id, started_at, start_ns)
    except BaseException:
        status = "failed"
        raise
    finally:
        if run_id is not None:
            _finish_run(engine, run_id, status, _elapsed_us(start_ns))
