"""Run the labelled set through both arms on the local database and clean up after it.

Every case gets a temporary inquiry (subject prefixed with `[eval] `) and a shared setup
outside the measurement: the rule-based extractor and fakes analyse it, then the golden
fields are saved as the user's correction, which runs the checks. An exception case is then
re-orchestrated once per repeat and arm (interleaved: workflow, orchestrator, workflow, ...)
with the arm's planner, the shared recommender and the template drafter; a case without an
exception never reaches the orchestration, so its single observation after the setup counts
for both arms. The temporary inquiries and their trace runs are deleted in `finally`, and a
run first deletes what an interrupted run left behind.
"""

import hashlib
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, delete
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.draft.drafter import FakeDrafter
from app.eval.cases import EvalCase
from app.eval.scoring import ArmName, ArmRun, observe, score
from app.inquiries.models import Inquiry
from app.orchestration.planning import Planner, RuleBasedPlanner
from app.parsing.extractor import ExtractionError
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


@dataclass(frozen=True)
class Arm:
    name: ArmName
    planner: Planner


class EvalRun(BaseModel):
    """One pass of the set: metadata, cases that could not be set up and every arm run.

    A case without an exception has one run per arm, with the same observation, and is
    listed in `not_orchestrated`.
    """

    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    finished_at: datetime
    provider: str
    model: str | None  # None for the rule-based fakes
    repeats: int
    planners: dict[ArmName, str]  # arm -> planner name
    recommender: str
    cases_sha256: str
    cases: list[str]  # case ids in run order
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
    repeats: int,
    pause_seconds: float,
    user: AuthUser,
    provider: str,
    model: str | None,
    cases_version: str,
) -> EvalRun:
    """Run every case through every arm `repeats` times; the database ends clean either way.

    `pause_seconds` separates consecutive arm calls (free-tier rate limits). LLM failures end
    in an observation with `failure`, not in an exception; unexpected errors propagate after
    the cleanup.
    """
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    started_at = datetime.now(UTC)
    setup_errors: list[tuple[str, str]] = []
    not_orchestrated: list[str] = []
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
            view, reason = _set_up(engine, case, inquiry_id, user)
            if reason is not None:
                logger.warning(
                    "case %d/%d · setup error · %s: %s", index, len(cases), case.id, reason
                )
                setup_errors.append((case.id, reason))
                continue
            assert view is not None

            if case.expected.checks_outcome != "exception":
                not_orchestrated.append(case.id)
                observation = observe(view)
                result = score(case, observation)
                for arm in arms:
                    runs.append(
                        ArmRun(
                            case_id=case.id,
                            arm=arm.name,
                            repeat=1,
                            observation=observation,
                            score=result,
                        )
                    )
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
                    arm_view = reorchestrate_inquiry(
                        engine, inquiry_id, arm.planner, recommender, FakeDrafter()
                    )
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
        repeats=repeats,
        planners={arm.name: arm.planner.name for arm in arms},
        recommender=recommender.name,
        cases_sha256=cases_version,
        cases=[case.id for case in cases],
        not_orchestrated=not_orchestrated,
        setup_errors=setup_errors,
        runs=runs,
    )


def _set_up(
    engine: Engine, case: EvalCase, inquiry_id: int, user: AuthUser
) -> tuple[AnalysisView | None, str | None]:
    """The view after the golden fields are saved, or the reason the setup failed."""
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
        return None, type(error).__name__
    outcome = None if view.checks is None else view.checks.outcome
    if outcome != case.expected.checks_outcome:
        return None, f"checks outcome {outcome}, expected {case.expected.checks_outcome}"
    return view, None


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
            select(Inquiry.id).where(col(Inquiry.subject).startswith(SUBJECT_PREFIX))
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
