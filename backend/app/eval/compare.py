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
"""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.eval.report import EvalReport
from app.eval.runner import EvalRun
from app.eval.scoring import FAILURE_ORCHESTRATION_PARTIAL, ArmName, ArmRun

DEFAULT_COST_FACTOR = 1.5

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
