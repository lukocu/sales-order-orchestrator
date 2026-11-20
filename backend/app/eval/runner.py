"""Run the labelled set through both arms on the local database and clean up after it.

Every case gets a temporary inquiry (subject prefixed with `[eval] `) and a shared setup
outside the measurement: the rule-based extractor and fakes analyse it, then the golden
fields are saved as the user's correction, which runs the checks. An adversarial case skips
the golden fields: the configured extractor parses it (once per case), the parsed price
fields are compared with its twin's, and a wrong parse is a scored miss, not a setup error.
An exception case is then re-orchestrated once per repeat and arm (interleaved: workflow,
orchestrator, workflow, ...) with the arm's planner, the shared recommender and the template
drafter; a case without an exception never reaches the orchestration, so its single
observation after the setup counts for both arms. The temporary inquiries and their trace
runs are deleted in `finally`, and a run first deletes what an interrupted run left behind.
A Postgres advisory lock held for the whole run keeps a second run (or the eval tests) from
starting meanwhile, so that sweep never deletes the inquiries of a run in progress.
"""

import hashlib
import logging
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, delete, text
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.draft.drafter import FakeDrafter
from app.eval.cases import CaseTag, EvalCase, ExpectedDecision
from app.eval.scoring import (
    FAILURE_PARSE_FAILED_PREFIX,
    FAILURE_PARSE_MISMATCH_PREFIX,
    FAILURE_UNEXPECTED_PREFIX,
    ArmName,
    ArmRun,
    Observation,
    observe,
    score,
)
from app.inquiries.models import Inquiry
from app.orchestration.planning import Planner, RuleBasedPlanner
from app.parsing.extractor import ExtractionError, InquiryExtractor
from app.parsing.fake import RuleBasedExtractor
from app.parsing.service import (
    SUBJECT_TYPE,
    AnalysisChanged,
    AnalysisView,
    analyze_inquiry,
    reorchestrate_inquiry,
    save_corrections,
)
from app.recommendation.recommender import FakeRecommender, Recommender
from app.tracing.models import TraceRun

logger = logging.getLogger(__name__)

SUBJECT_PREFIX = "[eval] "
# Key of the session-level advisory lock that makes eval runs exclusive ("eval" in ASCII).
RUN_LOCK_KEY = 0x6576616C


class EvalAlreadyRunning(RuntimeError):
    """Another eval run (or the eval tests) holds the run lock on this database."""


@dataclass(frozen=True)
class Arm:
    name: ArmName
    planner: Planner


class ParseCheck(BaseModel):
    """The parsed fields of an adversarial case against its twin's: the names that differ."""

    model_config = ConfigDict(extra="forbid")

    differing: list[str]  # empty when the parse matches


# Fields of an adversarial case that the parse is compared on.
PARSE_CHECKED_FIELDS = (
    "price_kind",
    "price_value",
    "quantity",
    "product_code",
    "substitute_allowed",
)


@dataclass(frozen=True)
class _Setup:
    """The result of a case's setup: a view to measure, a setup error, or a scored parse miss."""

    view: AnalysisView | None = None
    reason: str | None = None
    parse_check: ParseCheck | None = None
    miss: Observation | None = None  # a parse that failed or reached another checks outcome


class EvalRun(BaseModel):
    """One pass of the set: metadata, cases that could not be set up and every arm run.

    A case without an exception has one run per arm, with the same observation, and is
    listed in `not_orchestrated`; so is an adversarial case whose parse failed or reached
    another checks outcome.
    """

    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    finished_at: datetime
    provider: str
    model: str | None  # None for the rule-based fakes
    extractor: str  # parses the adversarial cases
    repeats: int
    planners: dict[ArmName, str]  # arm -> planner name
    recommender: str
    cases_sha256: str
    cases: list[str]  # case ids in run order
    expected: dict[str, ExpectedDecision]  # case id -> label
    tags: dict[str, list[CaseTag]] = {}  # case id -> tags
    adversarial_of: dict[str, str] = {}  # adversarial case id -> twin id
    parse_checks: dict[str, ParseCheck] = {}  # adversarial case id -> parse against the twin
    not_orchestrated: list[str]  # case ids without an exception: no arm run differs
    setup_errors: list[tuple[str, str]]  # (case id, reason)
    runs: list[ArmRun]


def cases_sha256(path: Path) -> str:
    """Version of a case file: the sha256 of its bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_eval(
    engine: Engine,
    cases: Sequence[EvalCase],
    arms: Sequence[Arm],
    recommender: Recommender,
    *,
    extractor: InquiryExtractor,
    repeats: int,
    pause_seconds: float,
    user: AuthUser,
    provider: str,
    model: str | None,
    cases_version: str,
) -> EvalRun:
    """Run every case through every arm `repeats` times; the database ends clean either way.

    `pause_seconds` separates consecutive arm calls (free-tier rate limits). LLM failures, and
    any other error raised by an arm's call, end in an observation with `failure`, so the
    runs collected so far are kept; an error in a case's setup propagates after the cleanup.
    `extractor` parses the adversarial cases only. Raises `EvalAlreadyRunning` when another
    run holds the run lock.
    """
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    with _run_lock(engine):
        return _run_locked(
            engine,
            cases,
            arms,
            recommender,
            extractor=extractor,
            repeats=repeats,
            pause_seconds=pause_seconds,
            user=user,
            provider=provider,
            model=model,
            cases_version=cases_version,
        )


@contextmanager
def _run_lock(engine: Engine) -> Iterator[None]:
    """Hold the eval run lock on a dedicated connection for the duration of the block."""
    with engine.connect() as connection:
        locked = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": RUN_LOCK_KEY}
        ).scalar_one()
        connection.commit()
        if not locked:
            raise EvalAlreadyRunning("Another eval run is in progress on this database")
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RUN_LOCK_KEY})
            connection.commit()


def _run_locked(
    engine: Engine,
    cases: Sequence[EvalCase],
    arms: Sequence[Arm],
    recommender: Recommender,
    *,
    extractor: InquiryExtractor,
    repeats: int,
    pause_seconds: float,
    user: AuthUser,
    provider: str,
    model: str | None,
    cases_version: str,
) -> EvalRun:
    started_at = datetime.now(UTC)
    setup_errors: list[tuple[str, str]] = []
    not_orchestrated: list[str] = []
    parse_checks: dict[str, ParseCheck] = {}
    runs: list[ArmRun] = []
    created: list[int] = []

    left_over = _eval_inquiry_ids(engine)
    if left_over:
        logger.info("Deleting %d inquiries left by an earlier eval run", len(left_over))
        _delete_inquiries(engine, left_over)

    try:
        for index, case in enumerate(cases, start=1):
            inquiry_id = _insert_inquiry(engine, case)
            created.append(inquiry_id)
            logger.info("case %d/%d · setup · %s", index, len(cases), case.id)
            setup = _set_up(engine, case, inquiry_id, user, extractor)
            if setup.parse_check is not None:
                parse_checks[case.id] = setup.parse_check
            if setup.reason is not None:
                logger.warning(
                    "case %d/%d · setup error · %s: %s", index, len(cases), case.id, setup.reason
                )
                setup_errors.append((case.id, setup.reason))
                continue
            if setup.miss is not None:
                logger.warning(
                    "case %d/%d · parse miss · %s: %s",
                    index,
                    len(cases),
                    case.id,
                    setup.miss.failure,
                )
                not_orchestrated.append(case.id)
                runs.extend(_shared_runs(case, arms, setup.miss))
                continue
            view = setup.view
            assert view is not None

            if case.expected.checks_outcome != "exception":
                not_orchestrated.append(case.id)
                runs.extend(_shared_runs(case, arms, observe(view)))
                continue

            first_call = True
            for repeat in range(1, repeats + 1):
                for arm in arms:
                    if not first_call and pause_seconds > 0:
                        time.sleep(pause_seconds)
                    first_call = False
                    logger.info(
                        "case %d/%d · %s · %d/%d", index, len(cases), arm.name, repeat, repeats
                    )
                    try:
                        arm_view = reorchestrate_inquiry(
                            engine, inquiry_id, arm.planner, recommender, FakeDrafter()
                        )
                    except Exception as error:
                        # Class name only, as the services log it: never inquiry content.
                        logger.warning(
                            "case %d/%d · %s · %d/%d failed with %s",
                            index,
                            len(cases),
                            arm.name,
                            repeat,
                            repeats,
                            type(error).__name__,
                        )
                        observation = _unexpected(error)
                    else:
                        observation = observe(arm_view)
                    runs.append(
                        ArmRun(
                            case_id=case.id,
                            arm=arm.name,
                            repeat=repeat,
                            observation=observation,
                            score=score(case, observation),
                        )
                    )
    finally:
        _delete_inquiries(engine, created)

    return EvalRun(
        started_at=started_at,
        finished_at=datetime.now(UTC),
        provider=provider,
        model=model,
        extractor=extractor.name,
        repeats=repeats,
        planners={arm.name: arm.planner.name for arm in arms},
        recommender=recommender.name,
        cases_sha256=cases_version,
        cases=[case.id for case in cases],
        expected={case.id: case.expected for case in cases},
        tags={case.id: case.tags for case in cases},
        adversarial_of={
            case.id: case.adversarial_of for case in cases if case.adversarial_of is not None
        },
        parse_checks=parse_checks,
        not_orchestrated=not_orchestrated,
        setup_errors=setup_errors,
        runs=runs,
    )


def _unexpected(error: Exception) -> Observation:
    """An arm call that raised: no decision, and its cost and time are unknown."""
    return Observation(
        checks_outcome="exception",  # only exception cases reach an arm call
        option_kind=None,
        policy_outcome=None,
        band=None,
        failure=FAILURE_UNEXPECTED_PREFIX + type(error).__name__,
        cost_usd=Decimal(0),
        cost_complete=False,
        duration_ms=0,
        input_tokens=0,
        output_tokens=0,
    )


def _shared_runs(case: EvalCase, arms: Sequence[Arm], observation: Observation) -> list[ArmRun]:
    """One run per arm with the same observation, for a case the arms cannot tell apart."""
    result = score(case, observation)
    return [
        ArmRun(case_id=case.id, arm=arm.name, repeat=1, observation=observation, score=result)
        for arm in arms
    ]


def _parse_miss(failure: str) -> Observation:
    """An adversarial case that could not be parsed: no checks, no decision."""
    return Observation(
        checks_outcome=None,
        option_kind=None,
        policy_outcome=None,
        band=None,
        failure=failure,
        cost_usd=Decimal(0),
        cost_complete=False,
        duration_ms=0,
        input_tokens=0,
        output_tokens=0,
    )


def _set_up_adversarial(
    engine: Engine,
    case: EvalCase,
    inquiry_id: int,
    user: AuthUser,
    extractor: InquiryExtractor,
) -> _Setup:
    """Parse the case once with `extractor`; a failed or diverging parse is a scored miss."""
    try:
        view = analyze_inquiry(
            engine,
            extractor,
            inquiry_id,
            user,
            RuleBasedPlanner(),
            FakeRecommender(),
            FakeDrafter(),
        )
    except ExtractionError as error:
        return _Setup(miss=_parse_miss(FAILURE_PARSE_FAILED_PREFIX + type(error).__name__))
    parse_check = ParseCheck(
        differing=[
            name
            for name in PARSE_CHECKED_FIELDS
            if getattr(view.fields, name) != getattr(case.fields, name)
        ]
    )
    outcome = None if view.checks is None else view.checks.outcome
    if outcome != case.expected.checks_outcome:
        miss = observe(view).model_copy(
            update={
                "failure": FAILURE_PARSE_MISMATCH_PREFIX + str(outcome),
                "failure_detail": None,
                # The checks outcome is wrong, so no decision of the orchestration counts.
                "option_kind": None,
                "policy_outcome": None,
                "band": None,
            }
        )
        return _Setup(parse_check=parse_check, miss=miss)
    return _Setup(view=view, parse_check=parse_check)


def _set_up(
    engine: Engine,
    case: EvalCase,
    inquiry_id: int,
    user: AuthUser,
    extractor: InquiryExtractor,
) -> _Setup:
    """The view to measure, or why the case cannot be measured.

    An adversarial case is parsed by `extractor`; any other case starts from its golden
    fields, saved as the user's correction.
    """
    if case.adversarial_of is not None:
        return _set_up_adversarial(engine, case, inquiry_id, user, extractor)
    try:
        analyzed = analyze_inquiry(
            engine,
            RuleBasedExtractor(),
            inquiry_id,
            user,
            RuleBasedPlanner(),
            FakeRecommender(),
            FakeDrafter(),
        )
        view = save_corrections(
            engine,
            inquiry_id,
            case.fields,
            reviewed=[],
            analyzed_at=analyzed.analyzed_at,
            user=user,
            planner=RuleBasedPlanner(),
            recommender=FakeRecommender(),
            drafter=FakeDrafter(),
        )
    except (ExtractionError, AnalysisChanged) as error:
        return _Setup(reason=type(error).__name__)
    outcome = None if view.checks is None else view.checks.outcome
    if outcome != case.expected.checks_outcome:
        return _Setup(reason=f"checks outcome {outcome}, expected {case.expected.checks_outcome}")
    return _Setup(view=view)


def _insert_inquiry(engine: Engine, case: EvalCase) -> int:
    inquiry = Inquiry(
        sender_name=case.sender_name,
        sender_email=case.sender_email,
        subject=SUBJECT_PREFIX + case.subject,
        body=case.body,
        received_at=case.received_at,
    )
    with Session(engine) as session:
        session.add(inquiry)
        session.commit()
        session.refresh(inquiry)
    assert inquiry.id is not None
    return inquiry.id


def _eval_inquiry_ids(engine: Engine) -> list[int]:
    with Session(engine) as session:
        ids = session.exec(
            # `source` too: inquiries read from the mailbox are never eval inquiries.
            select(Inquiry.id).where(
                col(Inquiry.subject).startswith(SUBJECT_PREFIX), col(Inquiry.source) == "sample"
            )
        ).all()
    return [i for i in ids if i is not None]


def _delete_inquiries(engine: Engine, inquiry_ids: Sequence[int]) -> None:
    """Delete the inquiries' trace runs and the inquiries (their analyses cascade)."""
    if not inquiry_ids:
        return
    with Session(engine) as session:
        session.exec(
            delete(TraceRun).where(
                col(TraceRun.subject_type) == SUBJECT_TYPE,
                col(TraceRun.subject_id).in_([str(i) for i in inquiry_ids]),
            )
        )
        session.exec(delete(Inquiry).where(col(Inquiry.id).in_(inquiry_ids)))
        session.commit()
