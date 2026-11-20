"""Comparison of two evaluation reports: what got worse, what is noise, what got dearer.

`compare` is a pure function over two `EvalReport`s, so it needs neither the database nor a
provider. The unit is a pair (case, arm): its hits are the repeats with a full hit.

- A *regression* (blocking) is a pair with fewer hits than in the baseline, or a baseline
  pair without any run in the current report.
- A *new failure* (blocking) is a run failure code (`observation.failure`) in the current
  runs of a pair that the baseline runs of that pair do not carry. `orchestration_partial`
  is only noted by the scoring, so it never counts here.
- A pair unstable in the baseline is *noise*: its hit drops and new failures are listed
  apart and never block. A pair unstable only in the current report is `new_instability`.
- *Improvements* and cost and time *warnings* are informational.

Two reports are comparable only when they ran the same case set with the same number of
repeats, and (unless `allow_model_change`) the same provider, model, extractor, planners and
recommender; otherwise the result carries `incompatibilities` and nothing else.

    python -m app.eval.compare
    python -m app.eval.compare --baseline eval_reports/<baseline>.json --current <report>.json

The command picks the current report (the newest in `--reports-dir`, unless `--current`) and
its baseline (the newest older report of the same case set, unless `--baseline`), prints the
comparison as Markdown and exits 0 (comparable, nothing blocking), 1 (a regression or a new
failure) or 2 (incompatible reports, no baseline, unreadable report or bad usage).
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.eval.report import NO_MODEL, EvalReport
from app.eval.runner import EvalRun
from app.eval.scoring import FAILURE_ORCHESTRATION_PARTIAL, ArmName, ArmRun

logger = logging.getLogger("app.eval.compare")

DEFAULT_COST_FACTOR = 1.5
DEFAULT_REPORTS_DIR = Path("eval_reports")

EXIT_OK = 0
EXIT_BLOCKING = 1
EXIT_UNUSABLE = 2

Pair = tuple[str, ArmName]  # case id, arm


class PairChange(BaseModel):
    """One (case, arm) pair whose hits or failure codes differ from the baseline.

    `failures` lists the new failure codes (empty for a change in hits only).
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    arm: ArmName
    baseline_hits: int
    baseline_total: int
    current_hits: int
    current_total: int
    failures: list[str] = []


class CostWarning(BaseModel):
    """The orchestrated mean of an arm that grew past the factor; `factor` is the ratio."""

    model_config = ConfigDict(extra="forbid")

    arm: ArmName
    metric: Literal["cost_usd_mean", "duration_ms_mean"]
    baseline: float
    current: float
    factor: float


class Comparison(BaseModel):
    """The result of `compare`; `incompatibilities` non-empty means nothing else was computed."""

    model_config = ConfigDict(extra="forbid")

    incompatibilities: list[str] = []
    regressions: list[PairChange] = []
    new_failures: list[PairChange] = []
    noise: list[PairChange] = []
    new_instability: list[PairChange] = []
    improvements: list[PairChange] = []
    warnings: list[CostWarning] = []

    @property
    def blocking(self) -> bool:
        """Whether the current report is worse than the baseline: a regression or a new failure."""
        return bool(self.regressions or self.new_failures)


def load_report(path: Path) -> EvalReport:
    """Read a JSON report. Raises `ValueError` naming the file when it is not a valid report."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return EvalReport.model_validate(_without_computed_rates(data))
    except (json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"{path} is not a valid evaluation report: {error}") from error


def _without_computed_rates(node: Any) -> Any:
    """Drop `rate` from every accuracy object: it is a computed field that the JSON carries
    but `Accuracy` (extra="forbid") does not accept back."""
    if isinstance(node, list):
        return [_without_computed_rates(item) for item in node]
    if isinstance(node, dict):
        is_accuracy = {"hits", "total", "rate"} <= node.keys()
        return {
            key: _without_computed_rates(value)
            for key, value in node.items()
            if not (is_accuracy and key == "rate")
        }
    return node


def compare(
    baseline: EvalReport,
    current: EvalReport,
    *,
    allow_model_change: bool = False,
    cost_factor: float = DEFAULT_COST_FACTOR,
) -> Comparison:
    """Compare a current report with the baseline, pair by pair (see the module docstring)."""
    incompatibilities = _incompatibilities(baseline.run, current.run, allow_model_change)
    if incompatibilities:
        return Comparison(incompatibilities=incompatibilities)

    base_runs = _group(baseline.run.runs)
    cur_runs = _group(current.run.runs)
    base_unstable = {(item.case_id, item.arm) for item in baseline.unstable}
    cur_unstable = {(item.case_id, item.arm) for item in current.unstable}

    result = Comparison()
    for pair in sorted(base_runs):
        before, after = base_runs[pair], cur_runs.get(pair, [])
        noisy = pair in base_unstable
        base_hits, cur_hits = _hits(before), _hits(after)

        if not after:
            result.regressions.append(_change(pair, before, after))
        elif cur_hits < base_hits:
            (result.noise if noisy else result.regressions).append(_change(pair, before, after))
        elif cur_hits > base_hits:
            result.improvements.append(_change(pair, before, after))

        new_codes = sorted(_failure_codes(after) - _failure_codes(before))
        if new_codes:
            target = result.noise if noisy else result.new_failures
            target.append(_change(pair, before, after, new_codes))

    for pair in sorted(cur_unstable - base_unstable):
        if pair in base_runs:
            result.new_instability.append(_change(pair, base_runs[pair], cur_runs.get(pair, [])))

    result.warnings = _cost_warnings(baseline, current, cost_factor)
    return result


def _incompatibilities(baseline: EvalRun, current: EvalRun, allow_model_change: bool) -> list[str]:
    """Differences that make two runs incomparable, as readable lines."""
    fields = ["cases_sha256", "repeats"]
    if not allow_model_change:
        fields += ["provider", "model", "extractor", "planners", "recommender"]
    return [
        f"{name}: baseline {getattr(baseline, name)!r}, current {getattr(current, name)!r}"
        for name in fields
        if getattr(baseline, name) != getattr(current, name)
    ]


def _group(runs: list[ArmRun]) -> dict[Pair, list[ArmRun]]:
    groups: dict[Pair, list[ArmRun]] = {}
    for run in runs:
        groups.setdefault((run.case_id, run.arm), []).append(run)
    return groups


def _hits(runs: list[ArmRun]) -> int:
    return sum(run.score.full_hit for run in runs)


def _failure_codes(runs: list[ArmRun]) -> set[str]:
    return {
        run.observation.failure
        for run in runs
        if run.observation.failure is not None
        and run.observation.failure != FAILURE_ORCHESTRATION_PARTIAL
    }


def _change(
    pair: Pair, before: list[ArmRun], after: list[ArmRun], failures: list[str] | None = None
) -> PairChange:
    return PairChange(
        case_id=pair[0],
        arm=pair[1],
        baseline_hits=_hits(before),
        baseline_total=len(before),
        current_hits=_hits(after),
        current_total=len(after),
        failures=failures or [],
    )


def _cost_warnings(
    baseline: EvalReport, current: EvalReport, cost_factor: float
) -> list[CostWarning]:
    """Orchestrated cost and time per run that grew past `cost_factor` times the baseline."""
    current_by_arm = {summary.arm: summary.orchestrated for summary in current.summaries}
    warnings: list[CostWarning] = []
    for summary in baseline.summaries:
        before, after = summary.orchestrated, current_by_arm.get(summary.arm)
        if before is None or after is None:
            continue
        if not (before.cost_complete and after.cost_complete):
            continue
        means: list[tuple[Literal["cost_usd_mean", "duration_ms_mean"], float, float]] = [
            ("cost_usd_mean", float(before.cost_usd_mean), float(after.cost_usd_mean)),
            ("duration_ms_mean", before.duration_ms_mean, after.duration_ms_mean),
        ]
        for metric, base_value, cur_value in means:
            if base_value == 0 or cur_value <= base_value * cost_factor:
                continue
            warnings.append(
                CostWarning(
                    arm=summary.arm,
                    metric=metric,
                    baseline=base_value,
                    current=cur_value,
                    factor=cur_value / base_value,
                )
            )
    return warnings


# --- Command ----------------------------------------------------------------------------


class _Unusable(Exception):
    """A reason to exit with code 2 (the message is logged)."""


def _cost_factor(value: str) -> float:
    factor = float(value)
    if factor <= 1:
        raise argparse.ArgumentTypeError("must be greater than 1")
    return factor


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.compare",
        description="Compare an evaluation report with a baseline, case by case.",
    )
    parser.add_argument("--current", type=Path, help="report to check (default: newest)")
    parser.add_argument("--baseline", type=Path, help="report to compare with (default: auto)")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="directory of JSON reports to choose from",
    )
    parser.add_argument(
        "--allow-model-change",
        action="store_true",
        help="compare reports of another provider, model, extractor, planners or recommender",
    )
    parser.add_argument(
        "--cost-factor",
        type=_cost_factor,
        default=DEFAULT_COST_FACTOR,
        help="warn when the orchestrated cost or time per run grows past this factor (> 1)",
    )
    parser.add_argument("--out", type=Path, help="also write the Markdown here")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parser().parse_args(argv)
    try:
        current_path, current, baseline_path, baseline = _select(args)
    except _Unusable as error:
        logger.error("%s", error)
        return EXIT_UNUSABLE

    comparison = compare(
        baseline,
        current,
        allow_model_change=args.allow_model_change,
        cost_factor=args.cost_factor,
    )
    markdown = render_comparison(comparison, baseline, current)
    logger.info("Current: %s; baseline: %s", current_path, baseline_path)
    sys.stdout.write(markdown)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")

    if comparison.incompatibilities:
        return EXIT_UNUSABLE
    return EXIT_BLOCKING if comparison.blocking else EXIT_OK


def _read(path: Path) -> EvalReport:
    try:
        return load_report(path)
    except (ValueError, OSError) as error:
        raise _Unusable(str(error)) from error


def _select(args: argparse.Namespace) -> tuple[Path, EvalReport, Path, EvalReport]:
    """The (path, report) of the current report and of its baseline."""
    in_dir: list[tuple[Path, EvalReport]] = []
    if args.current is None or args.baseline is None:
        in_dir = _reports_in(args.reports_dir)

    if args.current is not None:
        current_path, current = args.current, _read(args.current)
    elif in_dir:
        current_path, current = max(in_dir, key=lambda item: item[1].run.started_at)
    else:
        raise _Unusable(f"No evaluation report found in {args.reports_dir}.")

    if args.baseline is not None:
        return current_path, current, args.baseline, _read(args.baseline)

    candidates = [
        (path, report)
        for path, report in in_dir
        if report.run.cases_sha256 == current.run.cases_sha256
        and path.resolve() != current_path.resolve()
        and report.run.started_at < current.run.started_at
    ]
    if not candidates:
        raise _Unusable(
            f"No baseline for the case set {current.run.cases_sha256} in {args.reports_dir}: "
            "no older report of the same case set. Pass --baseline PATH."
        )
    baseline_path, baseline = max(candidates, key=lambda item: item[1].run.started_at)
    return current_path, current, baseline_path, baseline


def _reports_in(directory: Path) -> list[tuple[Path, EvalReport]]:
    """Every `*.json` in `directory` that is a report; the others are skipped with a warning."""
    reports: list[tuple[Path, EvalReport]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            reports.append((path, load_report(path)))
        except (ValueError, OSError) as error:
            logger.warning("Skipping %s: %s", path, error)
    return reports


# --- Markdown ---------------------------------------------------------------------------


def render_comparison(comparison: Comparison, baseline: EvalReport, current: EvalReport) -> str:
    """The comparison as Markdown: both reports, the verdict and one section per finding."""
    sections = [_header(baseline, current)]
    if comparison.incompatibilities:
        lines = ["## Incompatible reports", ""]
        lines += [f"- {line}" for line in comparison.incompatibilities]
        sections.append("\n".join(lines))
        return "\n\n".join(sections) + "\n"

    sections.append(f"**Result: {'REGRESSION' if comparison.blocking else 'OK'}**")
    sections += [
        _pairs("Regressions", comparison.regressions),
        _pairs("New failures", comparison.new_failures),
        _pairs("Noise", comparison.noise),
        _pairs("New instability", comparison.new_instability),
        _pairs("Improvements", comparison.improvements),
        _costs(comparison.warnings),
    ]
    return "\n\n".join(sections) + "\n"


def _header(baseline: EvalReport, current: EvalReport) -> str:
    lines = ["# Evaluation comparison"]
    for title, report in (("Baseline", baseline), ("Current", current)):
        run = report.run
        lines += [
            "",
            f"## {title}",
            "",
            f"- Date: {run.started_at:%Y-%m-%d %H:%M:%S} UTC",
            f"- Provider: `{run.provider}`",
            f"- Model: `{run.model or NO_MODEL}`",
            f"- Repeats: {run.repeats}",
            f"- Case set sha256: `{run.cases_sha256}`",
            f"- Cases: {len(run.cases)}",
        ]
    return "\n".join(lines)


def _pairs(title: str, entries: list[PairChange]) -> str:
    lines = [f"## {title}", ""]
    if not entries:
        lines.append("None found.")
        return "\n".join(lines)
    for entry in entries:
        line = (
            f"- `{entry.case_id}` ({entry.arm}): "
            f"{entry.baseline_hits}/{entry.baseline_total} -> "
            f"{entry.current_hits}/{entry.current_total}"
        )
        if entry.failures:
            line += " · " + ", ".join(f"`{code}`" for code in entry.failures)
        lines.append(line)
    return "\n".join(lines)


def _costs(warnings: list[CostWarning]) -> str:
    lines = ["## Cost and time", ""]
    if not warnings:
        lines.append("None found: no orchestrated mean grew past the factor.")
        return "\n".join(lines)
    for warning in warnings:
        lines.append(
            f"- {warning.arm} · {warning.metric}: {warning.baseline:g} -> "
            f"{warning.current:g} ({warning.factor:.2f}x)"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
