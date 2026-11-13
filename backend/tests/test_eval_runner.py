"""The eval runner on the database with fakes: label agreement, failures, cleanup, the CLI."""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.eval import __main__ as cli
from app.eval.cases import CASES_PATH, EvalCase, load_cases
from app.eval.runner import SUBJECT_PREFIX, Arm, EvalRun, cases_sha256, run_eval
from app.inquiries.models import Inquiry
from app.orchestration.planning import PlannerRateLimited, PlanningResult, RuleBasedPlanner
from app.orchestration.schema import PlanFacts
from app.recommendation.recommender import FakeRecommender
from app.settings import get_settings
from app.tracing.demo import PRICED_USAGE
from app.tracing.models import StepKind, TraceRun

EXCEPTION_CASE = "acme-abc100-substitute"


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
) -> EvalRun:
    return run_eval(
        engine,
        cases,
        [
            Arm(name="workflow", planner=RuleBasedPlanner()),
            orchestrator or Arm(name="orchestrator", planner=RuleBasedPlanner()),
        ],
        FakeRecommender(),
        repeats=1,
        pause_seconds=0,
        user=user,
        provider="fake",
        model=None,
        cases_version=cases_sha256(CASES_PATH),
    )


def _max_run_id(engine: Engine) -> int:
    with Session(engine) as session:
        return session.exec(select(func.max(TraceRun.id))).one() or 0


def _assert_clean(engine: Engine, runs_after: int) -> None:
    """No `[eval] ` inquiry is left, nor any inquiry run created after `runs_after`."""
    with Session(engine) as session:
        inquiries = session.exec(
            select(Inquiry.id).where(col(Inquiry.subject).startswith(SUBJECT_PREFIX))
        ).all()
        runs = session.exec(
            select(TraceRun.id).where(
                col(TraceRun.subject_type) == "inquiry", col(TraceRun.id) > runs_after
            )
        ).all()
    assert inquiries == []
    assert runs == []


def test_full_set_matches_the_labels_and_leaves_no_rows(
    migrated_engine: Engine, sales_user: AuthUser
) -> None:
    before = _max_run_id(migrated_engine)
    cases = _cases()

    result = _run(migrated_engine, cases, sales_user)

    assert result.setup_errors == []
    assert result.cases == [case.id for case in cases]
    workflow = [run for run in result.runs if run.arm == "workflow"]
    assert sorted(run.case_id for run in workflow) == sorted(case.id for case in cases)
    misses = [run.case_id for run in workflow if not run.score.full_hit]
    assert misses == []
    assert sorted(result.not_orchestrated) == sorted(
        case.id for case in cases if case.expected.checks_outcome != "exception"
    )
    assert result.planners == {"workflow": "fake", "orchestrator": "fake"}
    assert result.recommender == "rule-based"
    _assert_clean(migrated_engine, before)


def test_rate_limited_planner_is_a_failure_with_its_cost(
    migrated_engine: Engine, sales_user: AuthUser
) -> None:
    before = _max_run_id(migrated_engine)

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
    _assert_clean(migrated_engine, before)


def test_cleanup_after_an_unexpected_error(migrated_engine: Engine, sales_user: AuthUser) -> None:
    before = _max_run_id(migrated_engine)

    with pytest.raises(RuntimeError):
        _run(
            migrated_engine,
            _cases(EXCEPTION_CASE),
            sales_user,
            orchestrator=Arm(name="orchestrator", planner=BrokenPlanner()),
        )

    _assert_clean(migrated_engine, before)


def test_leftovers_of_an_interrupted_run_are_deleted(
    migrated_engine: Engine, sales_user: AuthUser
) -> None:
    before = _max_run_id(migrated_engine)
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
        session.add(
            TraceRun(
                subject_type="inquiry",
                subject_id=str(leftover.id),
                status="completed",
                started_at=datetime.now(UTC),
            )
        )
        session.commit()

    result = _run(migrated_engine, [], sales_user)

    assert result.runs == []
    _assert_clean(migrated_engine, before)


def test_cli_refuses_without_an_llm_provider(
    monkeypatch: pytest.MonkeyPatch, migrated_engine: Engine
) -> None:
    settings = get_settings().model_copy(update={"llm_provider": "fake", "llm_api_key": None})
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "get_engine", lambda: migrated_engine)

    assert cli.main(["--only", EXCEPTION_CASE]) == 2


def test_cli_runs_on_fakes_when_allowed(
    monkeypatch: pytest.MonkeyPatch, migrated_engine: Engine, tmp_path: Path
) -> None:
    settings = get_settings().model_copy(update={"llm_provider": "fake", "llm_api_key": None})
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "get_engine", lambda: migrated_engine)
    before = _max_run_id(migrated_engine)
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
    _assert_clean(migrated_engine, before)
    (md_path,) = out_dir.glob("*.md")
    (json_path,) = out_dir.glob("*.json")
    assert md_path.stem == json_path.stem
    assert md_path.stem.endswith("-fake-none")
    markdown = md_path.read_text(encoding="utf-8")
    assert "## Arm comparison" in markdown
    assert "| Arm | Full accuracy |" in markdown
    assert "## Cases" in markdown
    assert f"| {EXCEPTION_CASE} |" in markdown
