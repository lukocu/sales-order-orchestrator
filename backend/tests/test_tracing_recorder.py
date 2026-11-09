from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.tracing import LlmUsage, price_usage, run
from app.tracing.models import TraceRun, TraceStep

USAGE = LlmUsage(
    provider="google",
    model="gemini-2.5-flash",
    input_tokens=1200,
    output_tokens=300,
    cache_read_tokens=200,
    raw={"promptTokenCount": 1200, "candidatesTokenCount": 300},
)


class BoomError(Exception):
    pass


def _subject() -> str:
    return f"test-{uuid4()}"


def _run(engine: Engine, run_id: int) -> TraceRun:
    with Session(engine) as session:
        return session.get_one(TraceRun, run_id)


def _steps(engine: Engine, run_id: int) -> list[TraceStep]:
    with Session(engine) as session:
        statement = select(TraceStep).where(TraceStep.run_id == run_id).order_by(col(TraceStep.id))
        return list(session.exec(statement).all())


def test_completed_run_has_duration_and_utc_start(migrated_engine: Engine) -> None:
    with run(migrated_engine, subject_type="test", subject_id=_subject()) as r:
        assert _run(migrated_engine, r.id).status == "running"

    stored = _run(migrated_engine, r.id)
    assert stored.status == "completed"
    assert stored.duration_us is not None
    assert stored.duration_us >= 0
    assert stored.started_at.utcoffset() == timedelta(0)


def test_deterministic_step_is_not_applicable_with_zero_tokens(migrated_engine: Engine) -> None:
    with (
        run(migrated_engine, subject_type="test", subject_id=_subject()) as r,
        r.step("normalize", kind="deterministic"),
    ):
        pass

    [step] = _steps(migrated_engine, r.id)
    assert step.name == "normalize"
    assert step.kind == "deterministic"
    assert step.status == "ok"
    assert step.price_status == "not_applicable"
    assert step.cost_usd is None
    assert step.provider is None
    assert (step.input_tokens, step.output_tokens) == (0, 0)
    assert (step.cache_read_tokens, step.cache_write_tokens) == (0, 0)
    assert step.duration_us >= 0
    assert step.started_at.utcoffset() == timedelta(0)


def test_llm_step_stores_tokens_and_cost(migrated_engine: Engine) -> None:
    with (
        run(migrated_engine, subject_type="test", subject_id=_subject()) as r,
        r.step("parse", kind="llm") as s,
    ):
        s.record_usage(USAGE)

    [step] = _steps(migrated_engine, r.id)
    expected = price_usage(USAGE)
    assert step.status == "ok"
    assert (step.provider, step.model) == ("google", "gemini-2.5-flash")
    assert (step.input_tokens, step.output_tokens) == (1200, 300)
    assert (step.cache_read_tokens, step.cache_write_tokens) == (200, 0)
    assert step.price_status == "priced"
    assert expected.cost_usd is not None
    assert step.cost_usd == expected.cost_usd
    assert step.cost_usd > Decimal(0)
    assert step.price_source == expected.source
    assert step.raw_usage == USAGE.raw


def test_failing_step_is_recorded_and_exception_propagates(migrated_engine: Engine) -> None:
    with (
        pytest.raises(BoomError),
        run(migrated_engine, subject_type="test", subject_id=_subject()) as r,
        r.step("parse", kind="llm") as s,
    ):
        s.record_usage(USAGE)
        raise BoomError

    [step] = _steps(migrated_engine, r.id)
    assert step.status == "failed"
    assert step.error_type == "BoomError"
    assert step.price_status == "priced"
    assert _run(migrated_engine, r.id).status == "failed"


def test_failing_run_keeps_earlier_steps(migrated_engine: Engine) -> None:
    with (
        pytest.raises(BoomError),
        run(migrated_engine, subject_type="test", subject_id=_subject()) as r,
    ):
        with r.step("first", kind="deterministic"):
            pass
        with r.step("second", kind="llm") as s:
            s.record_usage(USAGE)
        raise BoomError

    stored = _run(migrated_engine, r.id)
    assert stored.status == "failed"
    assert stored.duration_us is not None
    assert [(step.name, step.status) for step in _steps(migrated_engine, r.id)] == [
        ("first", "ok"),
        ("second", "ok"),
    ]


def test_record_usage_in_deterministic_step_is_rejected(migrated_engine: Engine) -> None:
    with (
        pytest.raises(ValueError, match="only allowed in llm steps"),
        run(migrated_engine, subject_type="test", subject_id=_subject()) as r,
        r.step("normalize", kind="deterministic") as s,
    ):
        s.record_usage(USAGE)

    [step] = _steps(migrated_engine, r.id)
    assert step.status == "failed"
    assert step.error_type == "ValueError"
    assert step.price_status == "not_applicable"


def test_second_record_usage_is_rejected(migrated_engine: Engine) -> None:
    with (
        pytest.raises(ValueError, match="already called"),
        run(migrated_engine, subject_type="test", subject_id=_subject()) as r,
        r.step("parse", kind="llm") as s,
    ):
        s.record_usage(USAGE)
        s.record_usage(USAGE)

    [step] = _steps(migrated_engine, r.id)
    assert step.status == "failed"
    assert step.input_tokens == USAGE.input_tokens  # the first usage is kept, not doubled


def test_llm_step_without_usage_is_unpriced(migrated_engine: Engine) -> None:
    with (
        pytest.raises(BoomError),
        run(migrated_engine, subject_type="test", subject_id=_subject()) as r,
        r.step("parse", kind="llm"),
    ):
        raise BoomError  # e.g. the model call failed before a response

    [step] = _steps(migrated_engine, r.id)
    assert step.status == "failed"
    assert step.price_status == "unpriced"
    assert step.cost_usd is None
    assert step.provider is None
    assert (step.input_tokens, step.output_tokens) == (0, 0)
