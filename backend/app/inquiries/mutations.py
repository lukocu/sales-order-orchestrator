"""Keep pending submissions and decisions safe from older processing requests.

The context follows a synchronous processing chain, including nested stage entry points.
Only short database transactions take locks; providers run outside them. Writers must call
``check_mutation`` under their analysis lock before either storing or deleting results.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from inspect import signature
from typing import cast

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.draft.models import InquiryDraft, InquiryDraftDecision
from app.inquiries.models import Inquiry
from app.parsing.models import InquiryAnalysis


class MutationConflict(Exception):
    """Processing cannot change a pending submission or a subsequent decision."""


class AwaitingSupervisor(MutationConflict):
    def __init__(self) -> None:
        super().__init__("Inquiry awaiting supervisor decision")


class InquiryChanged(MutationConflict):
    def __init__(self) -> None:
        super().__init__("Inquiry changed, reload")


@dataclass(frozen=True)
class _Mutation:
    engine: Engine
    inquiry_id: int
    decision_id: int | None


_current: ContextVar[_Mutation | None] = ContextVar("inquiry_mutation", default=None)


def _decision_id(session: Session, inquiry_id: int) -> int | None:
    return session.exec(
        select(InquiryDraftDecision.id)
        .where(col(InquiryDraftDecision.inquiry_id) == inquiry_id)
        .order_by(col(InquiryDraftDecision.id).desc())
        .limit(1)
    ).first()


def check_mutation(session: Session, inquiry_id: int) -> None:
    """Check under the caller's analysis lock, before any business-data write.

    A watermark also protects submit -> reject/approve -> late write, when the raw pending
    status alone would already allow a new operation. Direct private storage calls without
    a chain still enforce the pending-state restriction.
    """
    status = session.exec(
        select(InquiryDraft.status).where(col(InquiryDraft.inquiry_id) == inquiry_id)
    ).first()
    if status == "awaiting_supervisor":
        raise AwaitingSupervisor
    current = _current.get()
    if (
        current is not None
        and current.engine is session.get_bind()
        and current.inquiry_id == inquiry_id
        and _decision_id(session, inquiry_id) != current.decision_id
    ):
        raise InquiryChanged


@contextmanager
def _mutation(engine: Engine, inquiry_id: int) -> Iterator[None]:
    inherited = _current.get()
    if inherited is not None and (
        inherited.engine is not engine or inherited.inquiry_id != inquiry_id
    ):
        inherited = None
    with Session(engine) as session:
        # A stable parent lock serializes the absence of the first analysis as well.
        # NO KEY UPDATE still serializes creators, but permits FK KEY SHARE locks acquired
        # by a decision holding the analysis lock (avoids an implicit parent/child deadlock).
        session.exec(
            select(Inquiry).where(col(Inquiry.id) == inquiry_id).with_for_update(key_share=True)
        ).first()
        session.exec(
            select(InquiryAnalysis)
            .where(col(InquiryAnalysis.inquiry_id) == inquiry_id)
            .with_for_update()
        ).first()
        check_mutation(session, inquiry_id)
        current = inherited or _Mutation(engine, inquiry_id, _decision_id(session, inquiry_id))
    token = _current.set(current)
    try:
        yield
    finally:
        _current.reset(token)


def mutating_inquiry[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Guard a public service entry, preserving its signature and inherited watermark.

    All services name the database and key ``engine`` and ``inquiry_id``. Binding once at
    decoration time also supports the parser's different positional argument order.
    """
    parameters = signature(function)

    @wraps(function)
    def guarded(*args: P.args, **kwargs: P.kwargs) -> R:
        arguments = parameters.bind(*args, **kwargs).arguments
        engine = cast(Engine, arguments["engine"])
        inquiry_id = cast(int, arguments["inquiry_id"])
        with _mutation(engine, inquiry_id):
            return function(*args, **kwargs)

    return guarded
