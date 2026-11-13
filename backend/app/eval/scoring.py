"""Scoring of evaluation runs: pure functions, no database.

`observe` turns the analysis view read after one arm's run into the observed decision plus
its cost, time and tokens; `score` compares it with the case's label; `summarize` and
`instability` aggregate the runs of one arm. Cost, time and tokens are sums over the
orchestration, recommendation and policy runs: the stages an arm runs one after another
(agents inside the orchestration run in parallel, so the run's wall time is used, not the
sum of its steps).
"""

from collections import Counter
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field

from app.checks.schema import Outcome
from app.eval.cases import EvalCase
from app.parsing.service import AnalysisView
from app.policy.schema import PolicyOutcome
from app.recommendation.schema import ConfidenceBand, OptionKind
from app.tracing.summary import RunSummary

ArmName = Literal["workflow", "orchestrator"]

# `Numeric(16, 10)` of `trace_steps.cost_usd`.
COST_QUANTUM = Decimal("0.0000000001")

FAILURE_ORCHESTRATION_PARTIAL = "orchestration_partial"
FAILURE_CHOICE_REJECTED = "choice_rejected"
FAILURE_MISSING_RUN = "missing_run"


class Observation(BaseModel):
    """What one arm's run ended in.

    `failure` is one of `orchestration_failed:<code>`, `orchestration_partial`,
    `recommender_failed:<code>`, `choice_rejected` or `missing_run` (an expected stage, or
    the trace run of a stage, is missing). `orchestration_partial` is only noted: a partial
    orchestration that still reaches the expected decision is a hit.
    """

    model_config = ConfigDict(extra="forbid")

    checks_outcome: Outcome | None  # None when the inquiry has no check result
    option_kind: OptionKind | None
    policy_outcome: PolicyOutcome | None
    band: ConfidenceBand | None  # of the chosen option; informational, not scored
    failure: str | None
    cost_usd: Decimal
    cost_complete: bool  # false when a step is unpriced or a stage's run is missing
    duration_ms: int
    input_tokens: int
    output_tokens: int


class Score(BaseModel):
    """An observation against its label; component hits are None for a non-exception case."""

    model_config = ConfigDict(extra="forbid")

    checks_hit: bool
    option_hit: bool | None
    policy_hit: bool | None
    full_hit: bool


class ArmRun(BaseModel):
    """One repeat of one case in one arm."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    arm: ArmName
    repeat: int  # 1-based
    observation: Observation
    score: Score


class Accuracy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hits: int
    total: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rate(self) -> float | None:
        """Hits per scored run; None when nothing was scored."""
        return None if self.total == 0 else self.hits / self.total


class ArmSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arm: ArmName
    runs: int
    full: Accuracy
    option: Accuracy  # exception cases only
    policy: Accuracy  # exception cases only
    checks: Accuracy
    failures: dict[str, int]  # failure -> runs, sorted by failure
    cost_usd_total: Decimal
    cost_usd_mean: Decimal  # per run
    cost_complete: bool  # every run's cost is complete
    duration_ms_mean: float
    duration_ms_max: int
    input_tokens: int
    output_tokens: int


class ObservedDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repeat: int
    checks_outcome: Outcome | None
    option_kind: OptionKind | None
    policy_outcome: PolicyOutcome | None


class Instability(BaseModel):
    """A case whose repeats in one arm ended in different decisions."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    arm: ArmName
    decisions: list[ObservedDecision]  # by repeat


def _decision_failure(view: AnalysisView) -> str | None:
    """The failure that leaves an exception without a decision, if any."""
    orchestration = view.orchestration
    if orchestration is None:
        return FAILURE_MISSING_RUN
    if orchestration.status == "failed":
        code = "unknown" if orchestration.error is None else orchestration.error.code
        return f"orchestration_failed:{code}"
    recommendation = view.recommendation
    if recommendation is None:
        return FAILURE_MISSING_RUN
    if recommendation.error is not None:
        if recommendation.error.kind == "choice_rejected":
            return FAILURE_CHOICE_REJECTED
        return f"recommender_failed:{recommendation.error.code}"
    if recommendation.choice is None:
        return FAILURE_CHOICE_REJECTED
    if view.policy is None:
        return FAILURE_MISSING_RUN
    return None


def _stage_runs(view: AnalysisView) -> tuple[list[RunSummary], bool]:
    """Runs of the stages that are present, and whether any present stage lacks its run."""
    runs: list[RunSummary] = []
    missing = False
    for stage in (view.orchestration, view.recommendation, view.policy):
        if stage is None:
            continue
        if stage.run is None:
            missing = True
        else:
            runs.append(stage.run)
    return runs, missing


def observe(view: AnalysisView) -> Observation:
    """The decision, cost and time of the view read right after an arm's run.

    For an exception, a stage that should have run but is absent counts as `missing_run`
    and makes the cost incomplete; a non-exception inquiry has no stages to run.
    """
    checks_outcome = None if view.checks is None else view.checks.outcome
    exception = checks_outcome == "exception"

    option_kind: OptionKind | None = None
    band: ConfidenceBand | None = None
    recommendation = view.recommendation
    if recommendation is not None and recommendation.choice is not None:
        option_id = recommendation.choice.option_id
        chosen = next((o for o in recommendation.options if o.id == option_id), None)
        if chosen is not None:
            option_kind, band = chosen.kind, chosen.band
    policy_outcome = None if view.policy is None else view.policy.outcome

    runs, run_missing = _stage_runs(view)
    failure = _decision_failure(view) if exception else None
    stage_missing = failure == FAILURE_MISSING_RUN
    if failure is None and run_missing:
        failure = FAILURE_MISSING_RUN
    orchestration = view.orchestration
    if failure is None and orchestration is not None and orchestration.status == "partial":
        failure = FAILURE_ORCHESTRATION_PARTIAL

    return Observation(
        checks_outcome=checks_outcome,
        option_kind=option_kind,
        policy_outcome=policy_outcome,
        band=band,
        failure=failure,
        cost_usd=sum((r.totals.cost_usd for r in runs), Decimal(0)),
        cost_complete=not (run_missing or stage_missing)
        and all(r.totals.cost_complete for r in runs),
        duration_ms=round(sum(r.duration_ms or 0.0 for r in runs)),
        input_tokens=sum(r.totals.input_tokens for r in runs),
        output_tokens=sum(r.totals.output_tokens for r in runs),
    )


def score(case: EvalCase, obs: Observation) -> Score:
    """Hits against the label. An exception needs both the option kind and the verdict; a
    failure without a decision misses all three."""
    expected = case.expected
    checks_hit = obs.checks_outcome == expected.checks_outcome
    if expected.checks_outcome != "exception":
        return Score(checks_hit=checks_hit, option_hit=None, policy_hit=None, full_hit=checks_hit)
    option_hit = obs.option_kind is not None and obs.option_kind == expected.option_kind
    policy_hit = obs.policy_outcome is not None and obs.policy_outcome == expected.policy_outcome
    return Score(
        checks_hit=checks_hit,
        option_hit=option_hit,
        policy_hit=policy_hit,
        full_hit=option_hit and policy_hit,
    )


def _accuracy(hits: list[bool | None]) -> Accuracy:
    scored = [hit for hit in hits if hit is not None]
    return Accuracy(hits=sum(scored), total=len(scored))


def summarize(results: list[ArmRun]) -> ArmSummary:
    """Totals of one arm's runs. Raises `ValueError` for no runs or runs of several arms."""
    if not results:
        raise ValueError("There are no runs to summarize")
    arms = {run.arm for run in results}
    if len(arms) != 1:
        raise ValueError(f"Runs of one arm expected, got {sorted(arms)}")
    (arm,) = arms
    observations = [run.observation for run in results]
    scores = [run.score for run in results]
    total = sum((o.cost_usd for o in observations), Decimal(0))
    failures = Counter(o.failure for o in observations if o.failure is not None)
    durations = [o.duration_ms for o in observations]
    return ArmSummary(
        arm=arm,
        runs=len(results),
        full=_accuracy([s.full_hit for s in scores]),
        option=_accuracy([s.option_hit for s in scores]),
        policy=_accuracy([s.policy_hit for s in scores]),
        checks=_accuracy([s.checks_hit for s in scores]),
        failures=dict(sorted(failures.items())),
        cost_usd_total=total,
        cost_usd_mean=(total / len(results)).quantize(COST_QUANTUM),
        cost_complete=all(o.cost_complete for o in observations),
        duration_ms_mean=sum(durations) / len(durations),
        duration_ms_max=max(durations),
        input_tokens=sum(o.input_tokens for o in observations),
        output_tokens=sum(o.output_tokens for o in observations),
    )


def instability(results: list[ArmRun]) -> list[Instability]:
    """Cases whose repeats in one arm ended in different decisions, by case id and arm."""
    groups: dict[tuple[str, ArmName], list[ArmRun]] = {}
    for run in results:
        groups.setdefault((run.case_id, run.arm), []).append(run)
    unstable: list[Instability] = []
    for case_id, arm in sorted(groups):
        runs = groups[(case_id, arm)]
        decisions = [
            ObservedDecision(
                repeat=run.repeat,
                checks_outcome=run.observation.checks_outcome,
                option_kind=run.observation.option_kind,
                policy_outcome=run.observation.policy_outcome,
            )
            for run in sorted(runs, key=lambda r: r.repeat)
        ]
        distinct = {(d.checks_outcome, d.option_kind, d.policy_outcome) for d in decisions}
        if len(distinct) > 1:
            unstable.append(Instability(case_id=case_id, arm=arm, decisions=decisions))
    return unstable
