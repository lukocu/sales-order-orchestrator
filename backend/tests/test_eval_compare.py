"""Comparison of evaluation reports on hand-built runs: every rule of the gate. No database."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.eval.cases import ExpectedDecision
from app.eval.compare import Comparison, compare, load_report
from app.eval.report import EvalReport, build_report
from app.eval.runner import EvalRun
from app.eval.scoring import ArmName, ArmRun, Observation, Score

STARTED = datetime(2026, 11, 20, 18, 0, 0, tzinfo=UTC)
CASE = "acme-substitute"
OTHER = "beta-partial"
REAL_REPORT = (
    Path(__file__).parents[1]
    / "eval_reports"
    / "2026-11-20-openrouter-qwen-qwen3-30b-a3b-instruct-2507.json"
)

# one repeat: (full hit, failure code)
Repeat = tuple[bool, str | None]
HIT: Repeat = (True, None)
MISS: Repeat = (False, None)


def _arm_run(
    case_id: str,
    arm: ArmName,
    repeat: int,
    outcome: Repeat,
    *,
    cost: str = "0.001",
    duration_ms: int = 1000,
    cost_complete: bool = True,
) -> ArmRun:
    hit, failure = outcome
    return ArmRun(
        case_id=case_id,
        arm=arm,
        repeat=repeat,
        observation=Observation(
            checks_outcome="exception",
            option_kind="substitute" if hit else None,
            policy_outcome="no_approval_needed" if hit else None,
            band="HIGH" if hit else None,
            failure=failure,
            cost_usd=Decimal(cost),
            cost_complete=cost_complete,
            duration_ms=duration_ms,
            input_tokens=10,
            output_tokens=5,
        ),
        score=Score(checks_hit=True, option_hit=hit, policy_hit=hit, full_hit=hit),
    )


def _report(
    pairs: dict[tuple[str, ArmName], list[Repeat]],
    *,
    cost: str = "0.001",
    duration_ms: int = 1000,
    cost_complete: bool = True,
    **overrides: Any,
) -> EvalReport:
    runs = [
        _arm_run(
            case_id,
            arm,
            number,
            outcome,
            cost=cost,
            duration_ms=duration_ms,
            cost_complete=cost_complete,
        )
        for (case_id, arm), repeats in pairs.items()
        for number, outcome in enumerate(repeats, start=1)
    ]
    case_ids = list(dict.fromkeys(case_id for case_id, _ in pairs))
    fields: dict[str, Any] = {
        "started_at": STARTED,
        "finished_at": STARTED.replace(minute=30),
        "provider": "openrouter",
        "model": "qwen/qwen3",
        "extractor": "fake",
        "repeats": 3,
        "planners": {"workflow": "rule-based", "orchestrator": "openrouter"},
        "recommender": "openrouter",
        "cases_sha256": "abc123",
        "cases": case_ids,
        "expected": {
            case_id: ExpectedDecision(
                checks_outcome="exception",
                option_kind="substitute",
                policy_outcome="no_approval_needed",
            )
            for case_id in case_ids
        },
        "not_orchestrated": [],
        "setup_errors": [],
        "runs": runs,
    }
    fields.update(overrides)
    return build_report(EvalRun(**fields))


def _stable() -> dict[tuple[str, ArmName], list[Repeat]]:
    return {
        (CASE, "workflow"): [HIT, HIT, HIT],
        (CASE, "orchestrator"): [HIT, HIT, HIT],
        (OTHER, "orchestrator"): [HIT, HIT, HIT],
    }


def _with(
    base: dict[tuple[str, ArmName], list[Repeat]], **changes: list[Repeat]
) -> dict[tuple[str, ArmName], list[Repeat]]:
    """`base` with the orchestrator pair of the named case replaced (`acme=[...]`)."""
    names = {"acme": CASE, "beta": OTHER}
    updated = dict(base)
    for key, repeats in changes.items():
        updated[(names[key], "orchestrator")] = repeats
    return updated


def _pairs(entries: list[Any]) -> list[tuple[str, str]]:
    return [(entry.case_id, entry.arm) for entry in entries]


def test_no_change_is_clean_and_not_blocking() -> None:
    result = compare(_report(_stable()), _report(_stable()))

    assert result == Comparison()
    assert not result.blocking


def test_fewer_hits_is_a_blocking_regression() -> None:
    current = _report(_with(_stable(), acme=[HIT, HIT, MISS]))

    result = compare(_report(_stable()), current)

    assert _pairs(result.regressions) == [(CASE, "orchestrator")]
    entry = result.regressions[0]
    assert (entry.baseline_hits, entry.baseline_total) == (3, 3)
    assert (entry.current_hits, entry.current_total) == (2, 3)
    assert result.blocking
    # the new instability of the pair is only noted
    assert _pairs(result.new_instability) == [(CASE, "orchestrator")]


def test_regression_in_the_workflow_arm_blocks_too() -> None:
    pairs = _stable()
    pairs[(CASE, "workflow")] = [HIT, MISS, MISS]

    result = compare(_report(_stable()), _report(pairs))

    assert _pairs(result.regressions) == [(CASE, "workflow")]
    assert result.blocking


def test_pair_missing_from_the_current_report_is_a_regression() -> None:
    pairs = _stable()
    del pairs[(OTHER, "orchestrator")]

    result = compare(_report(_stable()), _report(pairs))

    assert _pairs(result.regressions) == [(OTHER, "orchestrator")]
    assert result.regressions[0].current_total == 0
    assert result.blocking


def test_new_failure_code_blocks_even_when_hits_hold() -> None:
    # a stable pair at 0/3 stays at 0/3, but one run now ends in a failure
    baseline = _report(_with(_stable(), acme=[MISS, MISS, MISS]))
    current = _report(_with(_stable(), acme=[MISS, MISS, (False, "orchestration_failed:timeout")]))

    result = compare(baseline, current)

    assert result.regressions == []
    assert _pairs(result.new_failures) == [(CASE, "orchestrator")]
    assert result.new_failures[0].failures == ["orchestration_failed:timeout"]
    assert result.blocking


def test_failure_code_already_in_the_baseline_is_not_new() -> None:
    failed: Repeat = (False, "recommender_failed:rate_limited")
    baseline = _report(_with(_stable(), acme=[HIT, HIT, failed]))
    current = _report(_with(_stable(), acme=[HIT, failed, HIT]))

    result = compare(baseline, current)

    assert result.new_failures == []
    assert not result.blocking


def test_orchestration_partial_is_only_noted() -> None:
    partial: Repeat = (True, "orchestration_partial")
    current = _report(_with(_stable(), acme=[HIT, HIT, partial]))

    result = compare(_report(_stable()), current)

    assert result.new_failures == []
    assert not result.blocking


def test_drop_on_a_pair_unstable_in_the_baseline_is_noise() -> None:
    baseline = _report(_with(_stable(), acme=[HIT, HIT, MISS]))
    current = _report(_with(_stable(), acme=[HIT, MISS, MISS]))

    result = compare(baseline, current)

    assert result.regressions == []
    assert _pairs(result.noise) == [(CASE, "orchestrator")]
    assert (result.noise[0].baseline_hits, result.noise[0].current_hits) == (2, 1)
    # unstable in both: not new
    assert result.new_instability == []
    assert not result.blocking


def test_new_failure_on_a_pair_unstable_in_the_baseline_is_noise() -> None:
    baseline = _report(_with(_stable(), acme=[HIT, HIT, MISS]))
    current = _report(_with(_stable(), acme=[HIT, HIT, (False, "orchestration_failed:timeout")]))

    result = compare(baseline, current)

    assert result.new_failures == []
    assert [entry.failures for entry in result.noise] == [["orchestration_failed:timeout"]]
    assert not result.blocking


def test_pair_unstable_only_in_the_current_report_is_new_instability() -> None:
    # 2/3 -> 2/3 on a pair that was stable at 0/3 and is now split 2/1: hits grow, no block
    baseline = _report(_with(_stable(), acme=[MISS, MISS, MISS]))
    current = _report(_with(_stable(), acme=[HIT, HIT, MISS]))

    result = compare(baseline, current)

    assert _pairs(result.new_instability) == [(CASE, "orchestrator")]
    assert not result.blocking


def test_more_hits_is_an_improvement() -> None:
    baseline = _report(_with(_stable(), acme=[HIT, MISS, MISS]))
    current = _report(_stable())

    result = compare(baseline, current)

    assert _pairs(result.improvements) == [(CASE, "orchestrator")]
    assert (result.improvements[0].baseline_hits, result.improvements[0].current_hits) == (1, 3)
    assert not result.blocking


def test_cost_and_time_above_the_factor_warn_without_blocking() -> None:
    baseline = _report(_stable(), cost="0.001", duration_ms=1000)
    current = _report(_stable(), cost="0.002", duration_ms=2000)

    result = compare(baseline, current)

    assert {(w.arm, w.metric) for w in result.warnings} == {
        ("workflow", "cost_usd_mean"),
        ("workflow", "duration_ms_mean"),
        ("orchestrator", "cost_usd_mean"),
        ("orchestrator", "duration_ms_mean"),
    }
    warning = next(w for w in result.warnings if w.metric == "duration_ms_mean")
    assert (warning.baseline, warning.current, warning.factor) == (1000.0, 2000.0, 2.0)
    assert not result.blocking


def test_cost_and_time_below_the_factor_do_not_warn() -> None:
    baseline = _report(_stable(), cost="0.001", duration_ms=1000)
    current = _report(_stable(), cost="0.0014", duration_ms=1400)

    assert compare(baseline, current).warnings == []


def test_cost_factor_is_configurable() -> None:
    baseline = _report(_stable(), cost="0.001", duration_ms=1000)
    current = _report(_stable(), cost="0.0014", duration_ms=1400)

    assert compare(baseline, current, cost_factor=1.2).warnings != []


def test_incomplete_cost_on_either_side_skips_the_warning() -> None:
    baseline = _report(_stable(), cost="0.001", duration_ms=1000)
    current = _report(_stable(), cost="0.005", duration_ms=5000, cost_complete=False)

    assert compare(baseline, current).warnings == []
    assert compare(current, baseline).warnings == []


def test_zero_baseline_mean_is_skipped() -> None:
    baseline = _report(_stable(), cost="0", duration_ms=0)
    current = _report(_stable(), cost="0.005", duration_ms=5000)

    assert compare(baseline, current).warnings == []


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"cases_sha256": "def456"}, "cases_sha256"),
        ({"repeats": 1}, "repeats"),
        ({"model": "other/model"}, "model"),
        ({"provider": "groq"}, "provider"),
    ],
)
def test_incompatible_reports_return_only_the_differences(
    override: dict[str, Any], field: str
) -> None:
    baseline = _report(_stable())
    current = _report(_with(_stable(), acme=[MISS, MISS, MISS]), **override)

    result = compare(baseline, current)

    assert len(result.incompatibilities) == 1
    assert result.incompatibilities[0].startswith(f"{field}:")
    assert result.regressions == [] and result.warnings == []
    assert not result.blocking


def test_allow_model_change_passes_the_model_but_not_the_case_set() -> None:
    baseline = _report(_stable())

    changed_model = _report(_stable(), model="other/model")
    assert compare(baseline, changed_model).incompatibilities
    assert compare(baseline, changed_model, allow_model_change=True) == Comparison()

    changed_cases = _report(_stable(), model="other/model", cases_sha256="def456", repeats=1)
    result = compare(baseline, changed_cases, allow_model_change=True)
    assert [line.split(":")[0] for line in result.incompatibilities] == [
        "cases_sha256",
        "repeats",
    ]


def test_lowering_one_hit_flips_blocking() -> None:
    """Break check: the same pair of reports, with one repeat's full hit lowered."""
    baseline = _report(_stable())
    current = _report(_stable())
    assert not compare(baseline, current).blocking

    broken = current.model_copy(deep=True)
    run = next(r for r in broken.run.runs if (r.case_id, r.arm) == (CASE, "orchestrator"))
    run.score.full_hit = False

    assert compare(baseline, broken).blocking


def test_load_report_names_the_file_on_a_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"run": {}}', encoding="utf-8")

    with pytest.raises(ValueError, match="broken.json"):
        load_report(path)


def test_baseline_report_compared_with_itself_is_clean() -> None:
    baseline = load_report(REAL_REPORT)
    current = load_report(REAL_REPORT)

    result = compare(baseline, current)

    assert result.incompatibilities == []
    assert result.regressions == []
    assert result.new_failures == []
    assert not result.blocking
