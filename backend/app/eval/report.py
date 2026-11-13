"""The report of one evaluation run: Markdown for a reader and JSON for re-analysis.

`write_report` writes both next to each other as `<YYYY-MM-DD>-<provider>-<model>.md` and
`.json`. The JSON holds the whole `EvalRun` with every repeat, the per-arm summaries and the
unstable cases; `Decimal` values serialize to strings, as in `tracing/summary.py`.

Accuracy counts every run of an arm: a case without an exception scores its checks outcome
in the full accuracy, while the option and verdict accuracy cover exception cases only.
Failures, cost, time and tokens count the orchestrated runs only (exception cases): a case
without an exception never reaches a measured stage, so its zero cost and time would dilute
the per-run means without telling the arms apart.
"""

import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.eval.cases import ExpectedDecision
from app.eval.runner import EvalRun
from app.eval.scoring import (
    Accuracy,
    ArmName,
    ArmRun,
    ArmSummary,
    Instability,
    instability,
    summarize,
)

NO_MODEL = "none"
NO_VALUE = "—"

_SLUG_UNSAFE = re.compile(r"[^a-z0-9.-]")

Decision = tuple[str | None, str | None, str | None]  # checks outcome, option kind, verdict


class ArmReport(BaseModel):
    """`all_runs` scores accuracy; `orchestrated` (exception cases only, None without any)
    measures failures, cost, time and tokens."""

    model_config = ConfigDict(extra="forbid")

    arm: ArmName
    all_runs: ArmSummary | None
    orchestrated: ArmSummary | None


class EvalReport(BaseModel):
    """The JSON report: the run as it was measured plus what the Markdown shows."""

    model_config = ConfigDict(extra="forbid")

    run: EvalRun
    summaries: list[ArmReport]
    unstable: list[Instability]


def build_report(run: EvalRun) -> EvalReport:
    summaries: list[ArmReport] = []
    for arm in _arms(run):
        arm_runs = [r for r in run.runs if r.arm == arm]
        orchestrated = [r for r in arm_runs if r.case_id not in run.not_orchestrated]
        summaries.append(
            ArmReport(
                arm=arm,
                all_runs=summarize(arm_runs) if arm_runs else None,
                orchestrated=summarize(orchestrated) if orchestrated else None,
            )
        )
    return EvalReport(run=run, summaries=summaries, unstable=instability(run.runs))


def write_report(run: EvalRun, out_dir: Path) -> tuple[Path, Path]:
    """Write the Markdown and JSON report into `out_dir` (created when missing).

    A name already taken in `out_dir` gets the start time appended (`-HHMMSS`).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(run)
    md_path, json_path = _paths(run, out_dir)
    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def slug(value: str) -> str:
    """Lowercase, with every character outside `[a-z0-9.-]` replaced by `-`."""
    return _SLUG_UNSAFE.sub("-", value.lower())


def _paths(run: EvalRun, out_dir: Path) -> tuple[Path, Path]:
    base = "-".join(
        (run.started_at.date().isoformat(), slug(run.provider), slug(run.model or NO_MODEL))
    )
    candidates = [base, f"{base}-{run.started_at:%H%M%S}"]
    candidates += [f"{base}-{run.started_at:%H%M%S}-{n}" for n in range(2, 100)]
    for stem in candidates:
        md_path, json_path = out_dir / f"{stem}.md", out_dir / f"{stem}.json"
        if not md_path.exists() and not json_path.exists():
            return md_path, json_path
    raise FileExistsError(f"No free report name for {base} in {out_dir}")


def _arms(run: EvalRun) -> list[ArmName]:
    arms = list(run.planners)
    arms += [r.arm for r in run.runs if r.arm not in arms]
    return list(dict.fromkeys(arms))


# --- Markdown ---------------------------------------------------------------------------


def render_markdown(report: EvalReport) -> str:
    run = report.run
    sections = [
        _metadata(run),
        _comparison(report),
        _cases(run),
        _unstable(report.unstable),
        _failures(run),
        _setup_errors(run),
        _methodology(run),
    ]
    return "\n\n".join(sections) + "\n"


def _metadata(run: EvalRun) -> str:
    orchestrated = len(run.cases) - len(run.not_orchestrated) - len(run.setup_errors)
    planners = ", ".join(f"{arm}: `{name}`" for arm, name in run.planners.items())
    lines = [
        "# Workflow vs orchestrator evaluation",
        "",
        f"- Date: {run.started_at:%Y-%m-%d %H:%M:%S} UTC "
        f"(finished {run.finished_at:%Y-%m-%d %H:%M:%S} UTC)",
        f"- Provider: `{run.provider}`",
        f"- Model: `{run.model or NO_MODEL}`",
        f"- Planners: {planners}",
        f"- Recommender: `{run.recommender}`",
        f"- Repeats: {run.repeats}",
        f"- Case set sha256: `{run.cases_sha256}`",
        f"- Cases: {len(run.cases)} ({orchestrated} with an exception, "
        f"{len(run.not_orchestrated)} without an exception, "
        f"{len(run.setup_errors)} setup errors)",
    ]
    return "\n".join(lines)


def _comparison(report: EvalReport) -> str:
    lines = [
        "## Arm comparison",
        "",
        "| Arm | Full accuracy | Option accuracy | Verdict accuracy | Failures "
        "| Cost total (USD) | Cost per run (USD) | Cost complete | Mean time | Max time "
        "| Tokens (in / out) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm in report.summaries:
        accuracy = arm.all_runs
        measured = arm.orchestrated
        cells = [
            arm.arm,
            _accuracy(accuracy.full) if accuracy else NO_VALUE,
            _accuracy(accuracy.option) if accuracy else NO_VALUE,
            _accuracy(accuracy.policy) if accuracy else NO_VALUE,
        ]
        if measured is None:
            cells += [NO_VALUE] * 7
        else:
            cells += [
                str(sum(measured.failures.values())),
                _usd(measured.cost_usd_total),
                _usd(measured.cost_usd_mean),
                "yes" if measured.cost_complete else "no",
                f"{measured.duration_ms_mean:.0f} ms",
                f"{measured.duration_ms_max} ms",
                f"{measured.input_tokens} / {measured.output_tokens}",
            ]
        lines.append(_row(cells))
    return "\n".join(lines)


def _cases(run: EvalRun) -> str:
    arms = _arms(run)
    header = ["Case", "Expected"]
    for arm in arms:
        header += [f"{arm} (majority)", f"{arm} hits"]
    lines = [
        "## Cases",
        "",
        "Observed decision is the most common one of the repeats, with its count; hits are "
        "full-decision hits out of the repeats.",
        "",
        _row(header),
        "|" + "---|" * len(header),
    ]
    setup_errors = dict(run.setup_errors)
    for case_id in run.cases:
        expected = run.expected.get(case_id)
        cells = [case_id, _expected_label(expected) if expected else NO_VALUE]
        if case_id in setup_errors:
            cells += ["setup error", NO_VALUE] * len(arms)
            lines.append(_row(cells))
            continue
        no_orchestration = case_id in run.not_orchestrated
        for arm in arms:
            case_runs = [r for r in run.runs if r.case_id == case_id and r.arm == arm]
            if not case_runs:
                cells += [NO_VALUE, NO_VALUE]
                continue
            decision, count = _majority(case_runs)
            label = f"{_decision_label(decision)} ({count}/{len(case_runs)})"
            if no_orchestration:
                label += ", no orchestration"
            hits = sum(r.score.full_hit for r in case_runs)
            cells += [label, f"{hits}/{len(case_runs)}"]
        lines.append(_row(cells))
    return "\n".join(lines)


def _unstable(unstable: list[Instability]) -> str:
    lines = ["## Unstable cases", ""]
    if not unstable:
        lines.append("None: every case ended in the same decision in all repeats of an arm.")
        return "\n".join(lines)
    lines += ["| Case | Arm | Decisions by repeat |", "|---|---|---|"]
    for item in unstable:
        decisions = "; ".join(
            f"{d.repeat}: {_decision_label((d.checks_outcome, d.option_kind, d.policy_outcome))}"
            for d in item.decisions
        )
        lines.append(_row([item.case_id, item.arm, decisions]))
    return "\n".join(lines)


def _failures(run: EvalRun) -> str:
    lines = ["## Failures", ""]
    failed = [r for r in run.runs if r.observation.failure is not None]
    if not failed:
        lines.append("None.")
        return "\n".join(lines)
    counts = Counter((r.arm, r.observation.failure) for r in failed)
    lines += ["| Arm | Failure | Runs |", "|---|---|---|"]
    for (arm, failure), runs in sorted(
        counts.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        lines.append(_row([arm, f"`{failure}`", str(runs)]))
    lines += ["", "| Case | Arm | Repeat | Failure |", "|---|---|---|---|"]
    for r in failed:
        lines.append(_row([r.case_id, r.arm, str(r.repeat), f"`{r.observation.failure}`"]))
    return "\n".join(lines)


def _setup_errors(run: EvalRun) -> str:
    lines = ["## Setup errors", ""]
    if not run.setup_errors:
        lines.append("None.")
        return "\n".join(lines)
    lines += ["| Case | Reason |", "|---|---|"]
    lines += [_row([case_id, reason]) for case_id, reason in run.setup_errors]
    return "\n".join(lines)


def _methodology(run: EvalRun) -> str:
    lines = [
        "## Methodology notes",
        "",
        "- Cost is list-price cost in USD, computed from token usage with genai-prices; "
        "it is not the provider's invoice. A run whose cost is not complete has an unpriced "
        "step or a missing stage run, so its cost is a lower bound.",
        "- Time is the sum of the wall times of the orchestration, recommendation and policy "
        "runs of one arm run (agents inside the orchestration run in parallel).",
        "- The parser is excluded from the comparison: both arms start from the golden fields "
        "of the case, saved as the user's correction before the measurement.",
        "- Cases without an exception never reach the orchestration, so they do not tell the "
        "arms apart: each has one run, shared by both arms. They count in the full accuracy "
        "(checks outcome against the label) but not in the option and verdict accuracy, "
        "which cover exception cases only.",
        "- Failures, cost, time and tokens in the arm comparison count only the orchestrated "
        "runs (exception cases, every repeat); the per-run cost divides by that number of "
        "runs.",
        "- A full hit on an exception case needs both the chosen option kind and the policy "
        "verdict to match the label. A failure without a decision misses both; a partial "
        "orchestration that still reaches the expected decision is a hit. The confidence band "
        "is not scored.",
        f"- Each exception case ran {run.repeats} time(s) per arm, interleaving the arms.",
    ]
    return "\n".join(lines)


def _majority(runs: list[ArmRun]) -> tuple[Decision, int]:
    """The most common decision of the repeats (the earliest repeat wins a tie)."""
    ordered = sorted(runs, key=lambda r: r.repeat)
    counts = Counter(
        (r.observation.checks_outcome, r.observation.option_kind, r.observation.policy_outcome)
        for r in ordered
    )
    decision, count = counts.most_common(1)[0]
    return decision, count


def _decision_label(decision: Decision) -> str:
    checks, option, verdict = decision
    if checks is None:
        return "no checks"
    if checks != "exception":
        return checks
    if option is None and verdict is None:
        return "exception · no decision"
    return f"exception · {option or NO_VALUE} · {verdict or NO_VALUE}"


def _expected_label(expected: ExpectedDecision) -> str:
    return _decision_label((expected.checks_outcome, expected.option_kind, expected.policy_outcome))


def _accuracy(accuracy: Accuracy) -> str:
    if accuracy.rate is None:
        return NO_VALUE
    return f"{accuracy.hits}/{accuracy.total} ({accuracy.rate:.0%})"


def _usd(value: Decimal) -> str:
    return f"{value.normalize():f}"


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |"
