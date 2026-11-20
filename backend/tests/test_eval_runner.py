"""The eval runner on the database with fakes: label agreement, failures, cleanup, the CLI."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.eval import __main__ as cli
from app.eval import runner
from app.eval.cases import CASES_PATH, EvalCase, load_cases
from app.eval.runner import (
    RUN_LOCK_KEY,
    SUBJECT_PREFIX,
    Arm,
    EvalAlreadyRunning,
    EvalRun,
    cases_sha256,
    run_eval,
)
from app.eval.scoring import score_against
from app.inquiries.models import Inquiry
from app.orchestration.planning import PlannerRateLimited, PlanningResult, RuleBasedPlanner
from app.orchestration.schema import PlanFacts
from app.parsing.extractor import ExtractionFailed, ExtractionResult, InquiryExtractor
from app.parsing.fake import RuleBasedExtractor
from app.recommendation.recommender import FakeRecommender
from app.settings import get_settings
from app.tracing.demo import PRICED_USAGE
from app.tracing.models import StepKind, TraceRun

EXCEPTION_CASE = "acme-abc100-substitute"
DISCOUNT_CASE = "acme-xyz300-discount"


class RateLimitedPlanner:
    """Answers 429 after the provider billed the call."""

    name = "groq"
    step_kind: StepKind = "llm"

    def plan(self, facts: PlanFacts) -> PlanningResult:
        raise PlannerRateLimited("groq answered 429", usage=PRICED_USAGE)


class BrokenPlanner:
    name = "broken"
    step_kind: StepKind = "llm"

    def plan(self, facts: PlanFacts) -> PlanningResult:
        raise RuntimeError("unexpected")


class StubExtractor:
    """The rule-based parse with some extraction fields replaced."""

    name = "fake"  # inquiry_analyses.extractor only accepts fake/groq/openrouter
    step_kind: StepKind = "deterministic"

    def __init__(self, **update: object) -> None:
        self.update = update

    def extract(self, subject: str, body: str, reference_date: date) -> ExtractionResult:
        parsed = RuleBasedExtractor().extract(subject, body, reference_date)
        extraction = parsed.extraction.model_copy(update=self.update)
        return ExtractionResult(extraction=extraction, usage=None)


class RaisingExtractor:
    name = "raising"
    step_kind: StepKind = "llm"

    def extract(self, subject: str, body: str, reference_date: date) -> ExtractionResult:
        raise ExtractionFailed("provider timed out")


@pytest.fixture
def created(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Ids of the inquiries the runner inserts, so cleanup checks see only this test's rows."""
    ids: list[int] = []
    insert = runner._insert_inquiry

    def recording(engine: Engine, case: EvalCase) -> int:
        inquiry_id = insert(engine, case)
        ids.append(inquiry_id)
        return inquiry_id

    monkeypatch.setattr(runner, "_insert_inquiry", recording)
    return ids


@pytest.fixture
def sales_user(migrated_engine: Engine) -> AuthUser:
    with Session(migrated_engine) as session:
        user = session.exec(select(User).where(col(User.username) == "sales")).one()
        return AuthUser.from_user(user)


def _cases(*ids: str) -> list[EvalCase]:
    cases = load_cases()
    return [case for case in cases if case.id in ids] if ids else cases


def _run(
    engine: Engine,
    cases: Sequence[EvalCase],
    user: AuthUser,
    *,
    orchestrator: Arm | None = None,
    extractor: InquiryExtractor | None = None,
) -> EvalRun:
    return run_eval(
        engine,
        cases,
        [
            Arm(name="workflow", planner=RuleBasedPlanner()),
            orchestrator or Arm(name="orchestrator", planner=RuleBasedPlanner()),
        ],
        FakeRecommender(),
        extractor=extractor or RuleBasedExtractor(),
        repeats=1,
        pause_seconds=0,
        user=user,
        provider="fake",
        model=None,
        cases_version=cases_sha256(CASES_PATH),
    )


def _adversarial(case_id: str) -> EvalCase:
    """An adversarial copy of a case: same fields and label, the e-mail parsed instead."""
    (twin,) = _cases(case_id)
    return twin.model_copy(
        update={
            "id": f"{case_id}-adversarial",
            "tags": ["adversarial"],
            "adversarial_of": case_id,
        }
    )


def _assert_clean(engine: Engine, inquiry_ids: Sequence[int]) -> None:
    """None of these inquiries is left, nor any trace run of them."""
    assert inquiry_ids
    with Session(engine) as session:
        inquiries = session.exec(select(Inquiry.id).where(col(Inquiry.id).in_(inquiry_ids))).all()
        runs = session.exec(
            select(TraceRun.id).where(
                col(TraceRun.subject_type) == "inquiry",
                col(TraceRun.subject_id).in_([str(i) for i in inquiry_ids]),
            )
        ).all()
    assert inquiries == []
    assert runs == []


def _cli_settings(monkeypatch: pytest.MonkeyPatch, engine: Engine, **update: object) -> None:
    settings = get_settings().model_copy(update=update)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "get_engine", lambda: engine)


def test_full_set_matches_the_labels_and_leaves_no_rows(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    cases = _cases()

    result = _run(migrated_engine, cases, sales_user, extractor=RuleBasedExtractor())

    assert result.setup_errors == []
    assert result.cases == [case.id for case in cases]
    workflow = [run for run in result.runs if run.arm == "workflow"]
    assert sorted(run.case_id for run in workflow) == sorted(case.id for case in cases)
    # The fake path is checked against its own target: the label, or a documented departure.
    targets = {case.id: case.rule_based or case.expected for case in cases}
    misses = [
        run.case_id
        for run in workflow
        if not score_against(targets[run.case_id], run.observation).full_hit
    ]
    assert misses == []
    assert sorted(result.not_orchestrated) == sorted(
        case.id for case in cases if case.expected.checks_outcome != "exception"
    )
    assert result.planners == {"workflow": "fake", "orchestrator": "fake"}
    assert result.recommender == "rule-based"
    assert result.extractor == "fake"
    assert len(created) == len(cases)
    _assert_clean(migrated_engine, created)


def test_adversarial_case_with_a_matching_parse_is_scored_normally(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    case = _adversarial(EXCEPTION_CASE)

    result = _run(migrated_engine, [case], sales_user)

    assert result.setup_errors == []
    assert result.extractor == "fake"
    assert result.adversarial_of == {case.id: EXCEPTION_CASE}
    assert result.parse_checks[case.id].differing == []
    assert result.not_orchestrated == []
    assert [run.arm for run in result.runs] == ["workflow", "orchestrator"]
    assert all(run.score.full_hit and run.observation.failure is None for run in result.runs)
    _assert_clean(migrated_engine, created)


def test_a_dropped_discount_is_listed_and_scored_against_the_twins_label(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    case = _adversarial(DISCOUNT_CASE)
    dropped = StubExtractor(price_kind="none", price_value=None, price_text=None)

    result = _run(migrated_engine, [case], sales_user, extractor=dropped)

    assert result.setup_errors == []
    assert result.extractor == "fake"
    assert result.parse_checks[case.id].differing == ["price_kind", "price_value"]
    assert len(result.runs) == 2
    for run in result.runs:
        # Without the discount nothing needs the supervisor: the label is missed.
        assert run.observation.checks_outcome == "exception"
        assert run.observation.failure is None
        assert run.score.policy_hit is False
        assert run.score.full_hit is False
    _assert_clean(migrated_engine, created)


def test_a_parse_that_reaches_another_checks_outcome_is_a_scored_miss(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    case = _adversarial(EXCEPTION_CASE)

    result = _run(migrated_engine, [case], sales_user, extractor=StubExtractor(quantity=1))

    assert result.setup_errors == []
    assert result.parse_checks[case.id].differing == ["quantity"]
    assert result.not_orchestrated == [case.id]
    assert [run.arm for run in result.runs] == ["workflow", "orchestrator"]
    for run in result.runs:
        failure = run.observation.failure
        assert failure is not None
        assert failure.startswith("parse_mismatch:")
        assert failure != "parse_mismatch:exception"
        assert run.observation.checks_outcome == failure.removeprefix("parse_mismatch:")
        assert run.observation.option_kind is None
        assert run.score.full_hit is False
    _assert_clean(migrated_engine, created)


def test_a_raising_extractor_is_a_scored_parse_failure(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    case = _adversarial(EXCEPTION_CASE)

    result = _run(migrated_engine, [case], sales_user, extractor=RaisingExtractor())

    assert result.setup_errors == []
    assert case.id not in result.parse_checks
    assert result.not_orchestrated == [case.id]
    assert len(result.runs) == 2
    for run in result.runs:
        assert run.observation.failure == "parse_failed:ExtractionFailed"
        assert run.observation.checks_outcome is None
        assert run.score.full_hit is False
    _assert_clean(migrated_engine, created)


def test_a_parse_failure_leaves_the_other_cases_running(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    cases = [*_cases(EXCEPTION_CASE), _adversarial(EXCEPTION_CASE)]

    result = _run(migrated_engine, cases, sales_user, extractor=RaisingExtractor())

    by_case = {run.case_id: run for run in result.runs if run.arm == "workflow"}
    assert by_case[EXCEPTION_CASE].score.full_hit  # golden fields: the extractor is not used
    assert by_case[f"{EXCEPTION_CASE}-adversarial"].observation.failure is not None
    assert len(created) == 2
    _assert_clean(migrated_engine, created)


def test_rate_limited_planner_is_a_failure_with_its_cost(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    result = _run(
        migrated_engine,
        _cases(EXCEPTION_CASE),
        sales_user,
        orchestrator=Arm(name="orchestrator", planner=RateLimitedPlanner()),
    )

    by_arm = {run.arm: run for run in result.runs}
    assert by_arm["workflow"].score.full_hit
    failed = by_arm["orchestrator"]
    assert failed.observation.failure == "orchestration_failed:rate_limited"
    assert failed.score.full_hit is False
    assert failed.observation.cost_usd > Decimal(0)
    assert failed.observation.input_tokens > 0
    _assert_clean(migrated_engine, created)


def test_unexpected_arm_error_is_a_failure_and_keeps_the_other_runs(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    result = _run(
        migrated_engine,
        _cases(EXCEPTION_CASE),
        sales_user,
        orchestrator=Arm(name="orchestrator", planner=BrokenPlanner()),
    )

    by_arm = {run.arm: run for run in result.runs}
    assert by_arm["workflow"].score.full_hit
    failed = by_arm["orchestrator"]
    assert failed.observation.failure == "unexpected:RuntimeError"
    assert failed.observation.cost_complete is False
    assert failed.score.full_hit is False
    _assert_clean(migrated_engine, created)


def test_cleanup_after_an_error_in_the_setup(
    monkeypatch: pytest.MonkeyPatch,
    migrated_engine: Engine,
    sales_user: AuthUser,
    created: list[int],
) -> None:
    def broken_set_up(*args: object) -> object:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(runner, "_set_up", broken_set_up)

    with pytest.raises(RuntimeError):
        _run(migrated_engine, _cases(EXCEPTION_CASE), sales_user)

    _assert_clean(migrated_engine, created)


def test_a_second_run_is_refused_while_one_holds_the_lock(
    migrated_engine: Engine, sales_user: AuthUser, created: list[int]
) -> None:
    with migrated_engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": RUN_LOCK_KEY})
        try:
            with pytest.raises(EvalAlreadyRunning):
                _run(migrated_engine, _cases(EXCEPTION_CASE), sales_user)
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RUN_LOCK_KEY})

    assert created == []  # refused before inserting anything


def test_leftovers_of_an_interrupted_run_are_deleted(
    migrated_engine: Engine, sales_user: AuthUser
) -> None:
    with Session(migrated_engine) as session:
        leftover = Inquiry(
            sender_name="Left over",
            sender_email="zakupy@acme.example",
            subject=f"{SUBJECT_PREFIX}left over",
            body="Left by an interrupted run.",
            received_at=datetime.now(UTC),
        )
        session.add(leftover)
        session.commit()
        session.refresh(leftover)
        leftover_id = leftover.id
        assert leftover_id is not None
        session.add(
            TraceRun(
                subject_type="inquiry",
                subject_id=str(leftover_id),
                status="completed",
                started_at=datetime.now(UTC),
            )
        )
        session.commit()

    result = _run(migrated_engine, [], sales_user)

    assert result.runs == []
    _assert_clean(migrated_engine, [leftover_id])


def test_cleanup_keeps_a_mailbox_inquiry_with_an_eval_subject(
    migrated_engine: Engine, sales_user: AuthUser
) -> None:
    with Session(migrated_engine) as session:
        mail = Inquiry(
            sender_name="Mail",
            sender_email="zakupy@acme.example",
            subject=f"{SUBJECT_PREFIX}from the mailbox",
            body="Read from the mailbox.",
            received_at=datetime.now(UTC),
            source="mailbox",
            external_id="f" * 64,
        )
        session.add(mail)
        session.commit()
        session.refresh(mail)
        mail_id = mail.id
    try:
        _run(migrated_engine, [], sales_user)

        with Session(migrated_engine) as session:
            assert session.get(Inquiry, mail_id) is not None
    finally:
        with Session(migrated_engine) as session:
            kept = session.get(Inquiry, mail_id)
            if kept is not None:
                session.delete(kept)
                session.commit()


def test_cli_refuses_without_an_llm_provider(
    monkeypatch: pytest.MonkeyPatch, migrated_engine: Engine
) -> None:
    _cli_settings(monkeypatch, migrated_engine, llm_provider="fake", llm_api_key=None)

    assert cli.main(["--only", EXCEPTION_CASE]) == 2


def test_cli_refuses_a_provider_without_a_key(
    monkeypatch: pytest.MonkeyPatch, migrated_engine: Engine
) -> None:
    _cli_settings(monkeypatch, migrated_engine, llm_provider="groq", llm_api_key=None)

    assert cli.main(["--only", EXCEPTION_CASE]) == 2


def test_cli_refuses_a_remote_database(monkeypatch: pytest.MonkeyPatch) -> None:
    # Never connected: the guard runs before the first query.
    remote = create_engine("postgresql://user:secret@db.example.com:5432/orchestrator")
    _cli_settings(monkeypatch, remote, llm_provider="fake", llm_api_key=None)

    assert cli.main(["--allow-fake", "--only", EXCEPTION_CASE]) == 2


def test_cli_runs_on_fakes_when_allowed(
    monkeypatch: pytest.MonkeyPatch, migrated_engine: Engine, tmp_path: Path, created: list[int]
) -> None:
    _cli_settings(monkeypatch, migrated_engine, llm_provider="fake", llm_api_key=None)
    out_dir = tmp_path / "reports"

    code = cli.main(
        [
            "--allow-fake",
            "--only",
            EXCEPTION_CASE,
            "--repeats",
            "1",
            "--pause-seconds",
            "0",
            "--out",
            str(out_dir),
        ]
    )

    assert code == 0
    _assert_clean(migrated_engine, created)
    (md_path,) = out_dir.glob("*.md")
    (json_path,) = out_dir.glob("*.json")
    assert md_path.stem == json_path.stem
    assert md_path.stem.endswith("-fake-none")
    markdown = md_path.read_text(encoding="utf-8")
    assert "## Arm comparison" in markdown
    assert "| Arm | Full accuracy |" in markdown
    assert "## Cases" in markdown
    assert f"| {EXCEPTION_CASE} |" in markdown
