"""Context semantics without PostgreSQL; lock/race integration lives in the main suite.

Can run independently with --confcutdir=tests/unit. The deliberately minimal SQLite tables
exercise actual status/history reads, not PostgreSQL's row-lock guarantees.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlmodel import Session

from app.inquiries.models import Inquiry
from app.inquiries.mutations import (
    AwaitingSupervisor,
    InquiryChanged,
    check_mutation,
    mutating_inquiry,
)
from app.parsing.models import InquiryAnalysis


@pytest.fixture
def engine() -> Iterator[Engine]:
    database = create_engine("sqlite://")
    with database.begin() as connection:
        for table in (
            Inquiry.metadata.tables["inquiries"],
            InquiryAnalysis.metadata.tables["inquiry_analyses"],
        ):
            columns = ", ".join(f'"{column.name}" TEXT' for column in table.columns)
            connection.execute(text(f'CREATE TABLE "{table.name}" ({columns})'))
        connection.execute(text("CREATE TABLE inquiry_drafts (inquiry_id INTEGER, status TEXT)"))
        connection.execute(
            text(
                "CREATE TABLE inquiry_draft_decisions (id INTEGER PRIMARY KEY, inquiry_id INTEGER)"
            )
        )
    yield database
    database.dispose()


def _submission(engine: Engine, inquiry_id: int, *, pending: bool) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO inquiry_draft_decisions (inquiry_id) VALUES (:id)"),
            {"id": inquiry_id},
        )
        if pending:
            connection.execute(
                text("INSERT INTO inquiry_drafts VALUES (:id, 'awaiting_supervisor')"),
                {"id": inquiry_id},
            )


def test_pending_status_prevents_entering_the_provider(engine: Engine) -> None:
    _submission(engine, 1, pending=True)

    @mutating_inquiry
    def operation(engine: Engine, inquiry_id: int) -> None:
        pytest.fail("Provider must not run")

    with pytest.raises(AwaitingSupervisor):
        operation(engine, inquiry_id=1)


@pytest.mark.parametrize("pending", [True, False], ids=["still_pending", "already_decided"])
def test_write_checks_the_original_decision_watermark(engine: Engine, pending: bool) -> None:
    @mutating_inquiry
    def operation(engine: Engine, inquiry_id: int) -> None:
        _submission(engine, inquiry_id, pending=pending)
        with Session(engine) as session:
            check_mutation(session, inquiry_id)

    with pytest.raises(AwaitingSupervisor if pending else InquiryChanged):
        operation(engine, 1)


def test_nested_stage_does_not_recapture_watermark(engine: Engine) -> None:
    @mutating_inquiry
    def downstream(engine: Engine, inquiry_id: int) -> None:
        pytest.fail("A changed chain must stop before the next provider")

    @mutating_inquiry
    def operation(engine: Engine, inquiry_id: int) -> None:
        _submission(engine, inquiry_id, pending=False)
        downstream(engine, inquiry_id)

    with pytest.raises(InquiryChanged):
        operation(engine, 1)


def test_context_is_reset_after_failure_for_a_new_request(engine: Engine) -> None:
    @mutating_inquiry
    def failing(engine: Engine, inquiry_id: int) -> None:
        _submission(engine, inquiry_id, pending=False)
        raise RuntimeError("provider failed")

    @mutating_inquiry
    def fresh(engine: Engine, inquiry_id: int) -> str:
        with Session(engine) as session:
            check_mutation(session, inquiry_id)
        return "new request"

    with pytest.raises(RuntimeError):
        failing(engine, 1)
    assert fresh(engine, 1) == "new request"


def test_parser_argument_order_and_return_value_are_preserved(engine: Engine) -> None:
    @mutating_inquiry
    def parser(engine: Engine, extractor: str, inquiry_id: int) -> str:
        return f"{extractor}:{inquiry_id}"

    assert parser(engine, "fake", 1) == "fake:1"
    assert parser(engine=engine, extractor="fake", inquiry_id=2) == "fake:2"


def test_other_inquiry_decisions_do_not_invalidate_this_chain(engine: Engine) -> None:
    @mutating_inquiry
    def operation(engine: Engine, inquiry_id: int) -> None:
        _submission(engine, 2, pending=False)
        with Session(engine) as session:
            check_mutation(session, inquiry_id)

    operation(engine, 1)


def test_successful_nested_stage_can_use_existing_history(engine: Engine) -> None:
    _submission(engine, 1, pending=False)

    @mutating_inquiry
    def downstream(engine: Engine, inquiry_id: int) -> int:
        with Session(engine) as session:
            check_mutation(session, inquiry_id)
        return inquiry_id

    @mutating_inquiry
    def operation(engine: Engine, inquiry_id: int) -> int:
        return downstream(engine, inquiry_id)

    assert operation(engine, 1) == 1
