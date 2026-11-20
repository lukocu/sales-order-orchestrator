"""Comparison of evaluation reports on hand-built runs: every rule of the gate. No database."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.eval.cases import CASES_PATH, ExpectedDecision
from app.eval.compare import Comparison, compare, load_report, main
from app.eval.report import EvalReport, build_report
from app.eval.runner import EvalRun, cases_sha256
from app.eval.scoring import ArmName, ArmRun, Observation, Score

STARTED = datetime(2026, 11, 20, 18, 0, 0, tzinfo=UTC)
CASE = "acme-substitute"
OTHER = "beta-partial"
REPORTS_DIR = Path(__file__).parents[1] / "eval_reports"
REAL_REPORT = REPORTS_DIR / "2026-11-20-openrouter-qwen-qwen3-30b-a3b-instruct-2507.json"

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
    # 0/3 -> 2/3: the pair was stable at 0/3 and is now split, so it is an improvement too
    baseline = _report(_with(_stable(), acme=[MISS, MISS, MISS]))
    current = _report(_with(_stable(), acme=[HIT, HIT, MISS]))

    result = compare(baseline, current)

    assert _pairs(result.new_instability) == [(CASE, "orchestrator")]
    assert _pairs(result.improvements) == [(CASE, "orchestrator")]
    assert not result.blocking


def test_a_pair_with_another_number_of_runs_is_a_regression() -> None:
    # 3/3 against 2/2: the hits hold, but a truncated pair cannot be compared hit for hit
    current = _report(_with(_stable(), acme=[HIT, HIT]))

    result = compare(_report(_stable()), current)

    assert _pairs(result.regressions) == [(CASE, "orchestrator")]
    assert (result.regressions[0].current_hits, result.regressions[0].current_total) == (2, 2)
    assert result.blocking


def test_a_pair_unstable_in_the_baseline_that_falls_to_no_hit_blocks() -> None:
    baseline = _report(_with(_stable(), acme=[HIT, HIT, MISS]))
    current = _report(_with(_stable(), acme=[MISS, MISS, MISS]))

    result = compare(baseline, current)

    assert _pairs(result.regressions) == [(CASE, "orchestrator")]
    assert result.noise == []
    assert result.blocking


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


# --- Command ----------------------------------------------------------------------------


def _day(days: int) -> dict[str, Any]:
    """Overrides that start a report `days` after the default one."""
    return {"started_at": STARTED + timedelta(days=days)}


def _write(directory: Path, name: str, report: EvalReport) -> Path:
    path = directory / name
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def _run(capsys: pytest.CaptureFixture[str], *args: object) -> tuple[int, str]:
    code = main([str(arg) for arg in args])
    return code, capsys.readouterr().out


def test_exit_0_for_identical_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "old.json", _report(_stable()))
    _write(tmp_path, "new.json", _report(_stable(), **_day(1)))

    code, out = _run(capsys, "--reports-dir", tmp_path)

    assert code == 0
    assert "**Result: OK**" in out


def test_exit_1_for_a_regression_that_names_the_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "old.json", _report(_stable()))
    _write(tmp_path, "new.json", _report(_with(_stable(), acme=[HIT, HIT, MISS]), **_day(1)))

    code, out = _run(capsys, "--reports-dir", tmp_path)

    assert code == 1
    assert "**Result: REGRESSION**" in out
    assert f"`{CASE}` (orchestrator): 3/3 -> 2/3" in out


def test_exit_1_for_a_new_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    baseline = _write(tmp_path, "old.json", _report(_with(_stable(), acme=[MISS, MISS, MISS])))
    failed = _with(_stable(), acme=[MISS, MISS, (False, "orchestration_failed:timeout")])
    current = _write(tmp_path, "new.json", _report(failed, **_day(1)))

    code, out = _run(capsys, "--baseline", baseline, "--current", current)

    assert code == 1
    assert "`orchestration_failed:timeout`" in out


def test_exit_2_for_another_case_set(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    baseline = _write(tmp_path, "old.json", _report(_stable()))
    current = _write(tmp_path, "new.json", _report(_stable(), cases_sha256="def456", **_day(1)))

    code, out = _run(capsys, "--baseline", baseline, "--current", current)

    assert code == 2
    assert "cases_sha256: baseline 'abc123', current 'def456'" in out
    assert "## Regressions" not in out


def test_exit_2_without_a_baseline_in_the_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    _write(tmp_path, "other.json", _report(_stable(), cases_sha256="def456"))
    _write(tmp_path, "new.json", _report(_stable(), **_day(1)))

    code, out = _run(capsys, "--reports-dir", tmp_path)

    assert code == 2
    assert out == ""
    assert "No baseline for the case set abc123" in caplog.text


def test_exit_2_for_an_empty_directory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(capsys, "--reports-dir", tmp_path)[0] == 2


def test_exit_2_for_a_model_change_unless_allowed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "old.json", _report(_stable()))
    _write(tmp_path, "new.json", _report(_stable(), model="other/model", **_day(1)))

    code, out = _run(capsys, "--reports-dir", tmp_path)
    assert code == 2
    assert "model: baseline 'qwen/qwen3', current 'other/model'" in out

    code, _ = _run(capsys, "--reports-dir", tmp_path, "--allow-model-change")
    assert code == 0


def test_exit_1_for_a_regression_with_a_model_change_allowed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "old.json", _report(_stable()))
    changed = _report(_with(_stable(), acme=[MISS, MISS, MISS]), model="other/model", **_day(1))
    _write(tmp_path, "new.json", changed)

    code, _ = _run(capsys, "--reports-dir", tmp_path, "--allow-model-change")

    assert code == 1


def test_exit_2_for_an_unreadable_explicit_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    good = _write(tmp_path, "good.json", _report(_stable()))
    broken = tmp_path / "broken.json"
    broken.write_text("not json", encoding="utf-8")

    assert _run(capsys, "--baseline", good, "--current", broken)[0] == 2
    assert "broken.json" in caplog.text
    assert _run(capsys, "--baseline", tmp_path / "missing.json", "--current", good)[0] == 2


def test_the_baseline_is_the_newest_matching_older_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    # the newest matching older report has a better pair than the oldest one, so only it blocks
    _write(tmp_path, "a-oldest.json", _report(_with(_stable(), acme=[MISS, MISS, MISS])))
    _write(tmp_path, "b-middle.json", _report(_stable(), **_day(1)))
    _write(tmp_path, "c-other-set.json", _report(_stable(), cases_sha256="def456", **_day(2)))
    (tmp_path / "d-notes.json").write_text('{"hello": 1}', encoding="utf-8")
    _write(tmp_path, "e-current.json", _report(_with(_stable(), acme=[HIT, HIT, MISS]), **_day(3)))

    code, out = _run(capsys, "--reports-dir", tmp_path)

    assert code == 1
    assert "- Date: 2026-11-21 18:00:00 UTC" in out  # the baseline: b-middle
    assert "- Date: 2026-11-23 18:00:00 UTC" in out  # the current: e-current
    assert "2026-11-20 18:00:00" not in out
    assert "d-notes.json" in caplog.text


def test_a_report_newer_than_the_current_one_is_not_a_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current = _write(tmp_path, "current.json", _report(_stable()))
    _write(tmp_path, "later.json", _report(_stable(), **_day(1)))

    code, _ = _run(capsys, "--reports-dir", tmp_path, "--current", current)

    assert code == 2


def test_explicit_baseline_and_current_ignore_the_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = _write(tmp_path, "old.json", _report(_stable()))
    current = _write(tmp_path, "mid.json", _report(_stable(), **_day(1)))
    _write(tmp_path, "newest.json", _report(_with(_stable(), acme=[MISS] * 3), **_day(2)))

    code, out = _run(capsys, "--baseline", baseline, "--current", current)

    assert code == 0
    assert "- Date: 2026-11-21 18:00:00 UTC" in out


def test_out_writes_the_markdown_that_goes_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "old.json", _report(_stable()))
    _write(tmp_path, "new.json", _report(_with(_stable(), acme=[HIT, MISS, MISS]), **_day(1)))
    out_path = tmp_path / "nested" / "dir" / "comparison.md"

    code, out = _run(capsys, "--reports-dir", tmp_path, "--out", out_path)

    assert code == 1
    assert out_path.read_text(encoding="utf-8") == out


def test_exit_2_when_the_out_file_cannot_be_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    _write(tmp_path, "old.json", _report(_stable()))
    _write(tmp_path, "new.json", _report(_stable(), **_day(1)))

    # a directory cannot be written as a file
    code, _ = _run(capsys, "--reports-dir", tmp_path, "--out", tmp_path)

    assert code == 2
    assert "Cannot write" in caplog.text


def test_exit_2_when_baseline_and_current_are_the_same_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = _write(tmp_path, "only.json", _report(_stable()))

    assert _run(capsys, "--baseline", report, "--current", report)[0] == 2


def test_a_report_with_a_naive_started_at_is_ordered_with_aware_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "old.json", _report(_stable()))  # aware
    _write(tmp_path, "new.json", _report(_stable(), started_at=datetime(2026, 11, 21, 18, 0, 0)))

    code, _ = _run(capsys, "--reports-dir", tmp_path)

    assert code == 0


def test_a_report_that_is_not_utf8_is_unreadable_and_named(tmp_path: Path) -> None:
    broken = tmp_path / "latin.json"
    broken.write_bytes(b"\xff\xfe")

    with pytest.raises(ValueError, match="latin.json"):
        load_report(broken)


def test_markdown_has_every_section_and_says_when_one_is_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "old.json", _report(_stable()))
    _write(tmp_path, "new.json", _report(_stable(), **_day(1)))

    _, out = _run(capsys, "--reports-dir", tmp_path)

    for title in (
        "Regressions",
        "New failures",
        "Noise",
        "New instability",
        "Improvements",
        "Cost and time",
    ):
        assert f"## {title}\n\nNone found" in out
    assert "- Case set sha256: `abc123`" in out
    assert "- Repeats: 3" in out


def test_cost_warning_appears_in_the_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "old.json", _report(_stable(), duration_ms=1000))
    _write(tmp_path, "new.json", _report(_stable(), duration_ms=2000, **_day(1)))

    code, out = _run(capsys, "--reports-dir", tmp_path)
    assert code == 0
    assert "orchestrator · duration_ms_mean: 1000 -> 2000 (2.00x)" in out

    code, out = _run(capsys, "--reports-dir", tmp_path, "--cost-factor", "2.5")
    assert code == 0
    assert "duration_ms_mean" not in out


@pytest.mark.parametrize("factor", ["1", "0.5", "abc", "nan", "inf"])
def test_a_cost_factor_of_one_or_less_is_rejected(
    factor: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--cost-factor", factor])

    assert raised.value.code == 2
    assert "--cost-factor" in capsys.readouterr().err


def test_exit_1_for_the_real_report_with_one_hit_lowered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Break check on the committed baseline: a copy with one hit lowered blocks."""
    baseline = _write(tmp_path, "baseline.json", load_report(REAL_REPORT))
    broken = load_report(REAL_REPORT)
    broken.run.started_at += timedelta(days=1)
    lowered = next(r for r in broken.run.runs if r.score.full_hit)
    lowered.score.full_hit = False
    current = _write(tmp_path, "broken.json", broken)

    code, out = _run(capsys, "--baseline", baseline, "--current", current)

    assert code == 1
    assert f"`{lowered.case_id}` ({lowered.arm})" in out


# --- Consistency of the committed baseline -----------------------------------------------


def test_latest_report_matches_the_case_file() -> None:
    """The newest committed report must have been run on the current cases.json.

    It is what `python -m app.eval.compare` picks as the baseline, so a change to cases.json
    without a new report stops CI on purpose.
    """
    reports: list[tuple[Path, EvalReport]] = []
    for path in sorted(REPORTS_DIR.glob("*.json")):
        try:
            reports.append((path, load_report(path)))
        except ValueError:  # a report in an older format; `compare` skips it too
            continue
    assert reports, f"No evaluation report in {REPORTS_DIR}: run `python -m app.eval --repeats 3`."

    path, latest = max(reports, key=lambda item: item[1].run.started_at)

    assert latest.run.cases_sha256 == cases_sha256(CASES_PATH), (
        f"cases.json changed since the latest report ({path.name}): run "
        "`python -m app.eval --repeats 3` and commit the new report."
    )
