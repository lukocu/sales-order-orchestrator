from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine, delete
from sqlmodel import Session, col

from app.tracing.models import RunStatus, TraceRun, TraceStep
from app.tracing.summary import get_run_summary

TEST_SUBJECT_TYPE = "test"
START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _delete_test_runs(migrated_engine: Engine) -> Iterator[None]:
    yield
    with Session(migrated_engine) as session:
        session.exec(delete(TraceRun).where(col(TraceRun.subject_type) == TEST_SUBJECT_TYPE))
        session.commit()


def _insert_run(
    engine: Engine,
    steps: list[dict[str, Any]],
    *,
    status: RunStatus = "completed",
    duration_us: int | None = 2_000_000,
) -> int:
    with Session(engine) as session:
        trace_run = TraceRun(
            subject_type=TEST_SUBJECT_TYPE,
            subject_id=f"test-{uuid4()}",
            status=status,
            started_at=START,
            duration_us=duration_us,
        )
        session.add(trace_run)
        session.commit()
        session.refresh(trace_run)
        assert trace_run.id is not None
        for fields in steps:
            values: dict[str, Any] = {
                "name": "step",
                "kind": "deterministic",
                "status": "ok",
                "price_status": "not_applicable",
                "started_at": START,
                "duration_us": 0,
            } | fields
            session.add(TraceStep(run_id=trace_run.id, **values))
            session.commit()  # one commit per step, so ids follow list order
        return trace_run.id


def _llm(**fields: Any) -> dict[str, Any]:
    return {"kind": "llm", "provider": "google", "model": "gemini-2.5-flash"} | fields


def test_totals_sum_tokens_cost_and_durations(migrated_engine: Engine) -> None:
    run_id = _insert_run(
        migrated_engine,
        [
            _llm(
                input_tokens=1000,
                output_tokens=100,
                cache_read_tokens=200,
                cost_usd=Decimal("0.0010000001"),
                price_status="priced",
                duration_us=2_000_000,
            ),
            _llm(
                input_tokens=500,
                output_tokens=50,
                cost_usd=Decimal("0.0020000002"),
                price_status="priced",
                started_at=START + timedelta(seconds=1),
                duration_us=2_000_000,
            ),
        ],
    )

    with Session(migrated_engine) as session:
        summary = get_run_summary(session, run_id)

    assert summary is not None
    assert summary.id == run_id
    assert summary.status == "completed"
    assert summary.duration_ms == 2000
    totals = summary.totals
    assert (totals.input_tokens, totals.output_tokens, totals.cache_read_tokens) == (1500, 150, 200)
    assert totals.cost_usd == Decimal("0.0030000003")
    assert totals.cost_complete is True
    assert totals.steps_duration_ms == 4000
    assert totals.duration_ms == 2000


def test_unpriced_step_makes_cost_incomplete(migrated_engine: Engine) -> None:
    run_id = _insert_run(
        migrated_engine,
        [
            _llm(input_tokens=10, cost_usd=Decimal("0.5"), price_status="priced"),
            _llm(input_tokens=20, price_status="unpriced", provider="openrouter"),
        ],
    )

    with Session(migrated_engine) as session:
        summary = get_run_summary(session, run_id)

    assert summary is not None
    assert summary.totals.cost_complete is False
    assert summary.totals.cost_usd == Decimal("0.5")  # the priced part only
    assert summary.totals.input_tokens == 30


def test_deterministic_only_run_costs_nothing(migrated_engine: Engine) -> None:
    run_id = _insert_run(migrated_engine, [{"duration_us": 1500}, {"duration_us": 500}])

    with Session(migrated_engine) as session:
        summary = get_run_summary(session, run_id)

    assert summary is not None
    totals = summary.totals
    assert totals.cost_complete is True
    assert totals.cost_usd == Decimal(0)
    assert (totals.input_tokens, totals.output_tokens, totals.cache_read_tokens) == (0, 0, 0)
    assert totals.steps_duration_ms == 2.0
    assert [step.price_status for step in summary.steps] == ["not_applicable"] * 2


def test_running_run_has_no_duration(migrated_engine: Engine) -> None:
    run_id = _insert_run(migrated_engine, [], status="running", duration_us=None)

    with Session(migrated_engine) as session:
        summary = get_run_summary(session, run_id)

    assert summary is not None
    assert summary.steps == []
    assert summary.duration_ms is None
    assert summary.totals.duration_ms is None
    assert summary.totals.steps_duration_ms == 0
    assert summary.totals.cost_complete is True


def test_steps_ordered_by_start_then_id(migrated_engine: Engine) -> None:
    run_id = _insert_run(
        migrated_engine,
        [
            {"name": "late", "started_at": START + timedelta(seconds=5)},
            {"name": "tie-first", "started_at": START},
            {"name": "tie-second", "started_at": START},
            {"name": "early", "started_at": START - timedelta(seconds=5)},
        ],
    )

    with Session(migrated_engine) as session:
        summary = get_run_summary(session, run_id)

    assert summary is not None
    assert [step.name for step in summary.steps] == ["early", "tie-first", "tie-second", "late"]
    # Compares instants, so it holds whatever time zone the database session uses.
    assert summary.steps[0].started_at == START - timedelta(seconds=5)


def test_missing_run_is_none(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        assert get_run_summary(session, -1) is None
