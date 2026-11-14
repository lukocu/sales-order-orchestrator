"""The evaluation report on a hand-built run: Markdown sections and numbers, JSON contents,
file names. No database."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.eval.cases import ExpectedDecision
from app.eval.report import slug, write_report
from app.eval.runner import EvalRun
from app.eval.scoring import ArmName, ArmRun, Observation, Score
from app.policy.schema import PolicyOutcome
from app.recommendation.schema import OptionKind

STARTED = datetime(2026, 11, 13, 9, 30, 15, tzinfo=UTC)
EXCEPTION_CASE = "acme-substitute"
STANDARD_CASE = "beta-standard"
BROKEN_CASE = "gamma-broken"
RATE_LIMITED = "orchestration_failed:rate_limited"


def _exception_run(
    arm: ArmName,
    repeat: int,
    *,
    cost: str,
    duration_ms: int,
    tokens: tuple[int, int],
    failure: str | None = None,
) -> ArmRun:
    option: OptionKind | None = None if failure else "substitute"
    verdict: PolicyOutcome | None = None if failure else "no_approval_needed"
    hit = failure is None
    return ArmRun(
        case_id=EXCEPTION_CASE,
        arm=arm,
        repeat=repeat,
        observation=Observation(
            checks_outcome="exception",
            option_kind=option,
            policy_outcome=verdict,
            band=None if failure else "HIGH",
            failure=failure,
            failure_detail=None if failure is None else "recommender_failed: groq answered 429",
            cost_usd=Decimal(cost),
            cost_complete=True,
            duration_ms=duration_ms,
            input_tokens=tokens[0],
            output_tokens=tokens[1],
        ),
        score=Score(checks_hit=True, option_hit=hit, policy_hit=hit, full_hit=hit),
    )


def _standard_run(arm: ArmName) -> ArmRun:
    return ArmRun(
        case_id=STANDARD_CASE,
        arm=arm,
        repeat=1,
        observation=Observation(
            checks_outcome="standard",
            option_kind=None,
            policy_outcome=None,
            band=None,
            failure=None,
            cost_usd=Decimal(0),
            cost_complete=True,
            duration_ms=0,
            input_tokens=0,
            output_tokens=0,
        ),
        score=Score(checks_hit=True, option_hit=None, policy_hit=None, full_hit=True),
    )


def _eval_run(model: str | None = "openai/gpt-oss-120b") -> EvalRun:
    return EvalRun(
        started_at=STARTED,
        finished_at=STARTED.replace(minute=45),
        provider="groq",
        model=model,
        repeats=2,
        planners={"workflow": "rule-based", "orchestrator": "groq"},
        recommender="groq",
        cases_sha256="abc123",
        cases=[EXCEPTION_CASE, STANDARD_CASE, BROKEN_CASE],
        expected={
            EXCEPTION_CASE: ExpectedDecision(
                checks_outcome="exception",
                option_kind="substitute",
                policy_outcome="no_approval_needed",
            ),
            STANDARD_CASE: ExpectedDecision(checks_outcome="standard"),
            BROKEN_CASE: ExpectedDecision(checks_outcome="needs_input"),
        },
        not_orchestrated=[STANDARD_CASE],
        setup_errors=[(BROKEN_CASE, "checks outcome standard, expected needs_input")],
        runs=[
            _exception_run("workflow", 1, cost="0.0001", duration_ms=1000, tokens=(10, 5)),
            _exception_run("orchestrator", 1, cost="0.0015", duration_ms=4000, tokens=(100, 50)),
            _exception_run("workflow", 2, cost="0.0001", duration_ms=3000, tokens=(10, 5)),
            _exception_run(
                "orchestrator",
                2,
                cost="0.0005",
                duration_ms=2000,
                tokens=(40, 0),
                failure=RATE_LIMITED,
            ),
            _standard_run("workflow"),
            _standard_run("orchestrator"),
        ],
    )


def _row(markdown: str, prefix: str) -> list[str]:
    (line,) = [line for line in markdown.splitlines() if line.startswith(prefix)]
    return [cell.strip() for cell in line.strip("|").split("|")]


def test_markdown_has_every_section_and_the_numbers(tmp_path: Path) -> None:
    md_path, _ = write_report(_eval_run(), tmp_path)
    markdown = md_path.read_text(encoding="utf-8")

    for heading in (
        "# Workflow vs orchestrator evaluation",
        "## Arm comparison",
        "## Cases",
        "## Unstable cases",
        "## Failures",
        "## Setup errors",
        "## Methodology notes",
    ):
        assert heading in markdown
    assert "- Model: `openai/gpt-oss-120b`" in markdown
    assert "- Case set sha256: `abc123`" in markdown
    assert "- Repeats: 2" in markdown

    # accuracy over every run; failures, cost, time, tokens over orchestrated runs only
    assert _row(markdown, "| workflow | 3/3") == [
        "workflow",
        "3/3 (100%)",
        "2/2 (100%)",
        "2/2 (100%)",
        "0",
        "0.0002",
        "0.0001",
        "yes",
        "2000 ms",
        "3000 ms",
        "20 / 10",
    ]
    assert _row(markdown, "| orchestrator | 2/3") == [
        "orchestrator",
        "2/3 (67%)",
        "1/2 (50%)",
        "1/2 (50%)",
        "1",
        "0.002",
        "0.001",
        "yes",
        "3000 ms",
        "4000 ms",
        "140 / 50",
    ]

    assert _row(markdown, f"| {EXCEPTION_CASE} | exception") == [
        EXCEPTION_CASE,
        "exception · substitute · no_approval_needed",
        "exception · substitute · no_approval_needed (2/2)",
        "2/2",
        "exception · substitute · no_approval_needed (1/2)",
        "1/2",
    ]
    standard = _row(markdown, f"| {STANDARD_CASE} |")
    assert standard[2] == "standard (1/1), no orchestration"
    assert _row(markdown, f"| {BROKEN_CASE} | needs_input")[2] == "setup error"

    assert (
        f"| {EXCEPTION_CASE} | orchestrator | 1: exception · substitute · no_approval_needed; "
        "2: exception · no decision |"
    ) in markdown
    assert f"| orchestrator | `{RATE_LIMITED}` | 1 |" in markdown
    assert (
        f"| {EXCEPTION_CASE} | orchestrator | 2 | `{RATE_LIMITED}` | "
        "recommender_failed: groq answered 429 |"
    ) in markdown
    assert "checks outcome standard, expected needs_input" in markdown
    assert "genai-prices" in markdown


def test_json_holds_every_run_and_the_summaries(tmp_path: Path) -> None:
    run = _eval_run()

    _, json_path = write_report(run, tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert len(data["run"]["runs"]) == len(run.runs)
    assert EvalRun.model_validate(data["run"]) == run
    assert data["run"]["runs"][0]["observation"]["cost_usd"] == "0.0001"
    by_arm = {summary["arm"]: summary for summary in data["summaries"]}
    assert by_arm["orchestrator"]["orchestrated"]["cost_usd_total"] == "0.0020"
    assert by_arm["orchestrator"]["all_runs"]["full"] == {"hits": 2, "total": 3, "rate": 2 / 3}
    assert [(u["case_id"], u["arm"]) for u in data["unstable"]] == [
        (EXCEPTION_CASE, "orchestrator")
    ]


def test_file_names_use_date_provider_and_model_and_avoid_collisions(tmp_path: Path) -> None:
    first = write_report(_eval_run(), tmp_path)
    second = write_report(_eval_run(), tmp_path)
    fake = write_report(_eval_run(model=None), tmp_path)

    assert [p.name for p in first] == [
        "2026-11-13-groq-openai-gpt-oss-120b.md",
        "2026-11-13-groq-openai-gpt-oss-120b.json",
    ]
    assert [p.name for p in second] == [
        "2026-11-13-groq-openai-gpt-oss-120b-093015.md",
        "2026-11-13-groq-openai-gpt-oss-120b-093015.json",
    ]
    assert fake[0].name == "2026-11-13-groq-none.md"


def test_slug() -> None:
    assert slug("openai/gpt-oss-120b") == "openai-gpt-oss-120b"
    assert slug("Llama 3.3:70B") == "llama-3.3-70b"
