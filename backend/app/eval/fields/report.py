"""The report of one field-eval run: Markdown for a reader and JSON for re-analysis.

`write_report` writes both next to each other as `<YYYY-MM-DD>-<provider>-<model>.md` and
`.json`. The JSON is the whole `FieldRun` (labels, parsed values, outcomes of every repeat), so
every table here can be rebuilt from it; `Decimal` values serialize to strings.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path

from app.eval.fields.cases import FieldCase, FieldTag
from app.eval.fields.runner import FieldObservation, FieldRun
from app.eval.fields.scoring import FIELD_NAMES, FieldOutcome, Tally, summarize
from app.eval.report import NO_MODEL, slug
from app.parsing.schema import FieldName, ParsedFields

NO_VALUE = "—"
_LETTER: dict[FieldOutcome, str] = {"hit": "h", "flagged_miss": "f", "silent_wrong": "S"}


def write_report(run: FieldRun, out_dir: Path) -> tuple[Path, Path]:
    """Write the Markdown and JSON report into `out_dir` (created when missing).

    A name already taken in `out_dir` gets the start time appended (`-HHMMSS`).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path, json_path = _paths(run, out_dir)
    md_path.write_text(render_markdown(run), encoding="utf-8")
    json_path.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def _paths(run: FieldRun, out_dir: Path) -> tuple[Path, Path]:
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


# --- Markdown ---------------------------------------------------------------------------


def render_markdown(run: FieldRun) -> str:
    summary = summarize(run.scored())
    sections = [
        _metadata(run),
        _per_field(summary.per_field),
        _silent_errors(run),
        _per_tag(summary.per_tag),
        _case_table(run),
        _unstable(run),
        _failures(run),
        _methodology(run),
    ]
    return "\n\n".join(sections) + "\n"


def _metadata(run: FieldRun) -> str:
    failed = sum(o.failure is not None for o in run.observations)
    tokens = [o for o in run.observations if o.input_tokens is not None]
    lines = [
        "# Parser field evaluation",
        "",
        f"- Date: {run.started_at:%Y-%m-%d %H:%M:%S} UTC "
        f"(finished {run.finished_at:%Y-%m-%d %H:%M:%S} UTC)",
        f"- Provider: `{run.provider}`",
        f"- Model: `{run.model or NO_MODEL}`",
        f"- Extractor: `{run.extractor}`",
        f"- Repeats: {run.repeats}",
        f"- Case set sha256: `{run.cases_sha256}`",
        f"- Cases: {len(run.cases)}",
        f"- Extractor calls: {len(run.observations)} ({failed} failed)",
    ]
    if tokens:
        lines.append(
            f"- Tokens (in / out): {sum(o.input_tokens or 0 for o in tokens)} / "
            f"{sum(o.output_tokens or 0 for o in tokens)}"
        )
    if run.observations:
        mean = sum(o.duration_ms for o in run.observations) / len(run.observations)
        lines.append(f"- Mean call time: {mean:.0f} ms")
    return "\n".join(lines)


def _per_field(per_field: dict[FieldName, Tally]) -> str:
    lines = [
        "## Accuracy per field",
        "",
        "Counts over (case, repeat, field); failed calls are not counted here.",
        "",
        "| Field | Hit | Flagged miss | Silent wrong | Total |",
        "|---|---|---|---|---|",
    ]
    for name in FIELD_NAMES:
        tally = per_field[name]
        lines.append(_tally_row(name, tally))
    return "\n".join(lines)


def _per_tag(per_tag: Mapping[FieldTag, Tally]) -> str:
    lines = [
        "## Accuracy per tag",
        "",
        "A tag counts only the field it is about, so an error there is not diluted by the "
        "other five fields; a case can carry several tags.",
        "",
    ]
    if not per_tag:
        lines.append("None.")
        return "\n".join(lines)
    lines += [
        "| Tag | Hit | Flagged miss | Silent wrong | Total |",
        "|---|---|---|---|---|",
    ]
    lines += [_tally_row(tag, per_tag[tag]) for tag in sorted(per_tag)]
    return "\n".join(lines)


def _tally_row(label: str, tally: Tally) -> str:
    return _row(
        [
            label,
            _count(tally.hits, tally.total),
            _count(tally.flagged_misses, tally.total),
            _count(tally.silent_wrongs, tally.total),
            str(tally.total),
        ]
    )


def _count(count: int, total: int) -> str:
    return f"{count} ({count / total:.0%})" if total else str(count)


def _silent_errors(run: FieldRun) -> str:
    """Every silent_wrong (case, field), grouped by the value the parser returned."""
    cases = {case.id: case for case in run.cases}
    found: dict[tuple[str, FieldName, str], list[int]] = defaultdict(list)
    for obs in run.observations:
        if obs.outcomes is None or obs.parsed is None:
            continue
        for name in FIELD_NAMES:
            if obs.outcomes[name] == "silent_wrong":
                found[(obs.case_id, name, _got(obs.parsed, name))].append(obs.repeat)
    lines = [
        "## SILENT ERRORS",
        "",
        "A field that is wrong, or lacks a flag its label requires, and was not marked "
        "uncertain: the failure this evaluation exists to find.",
        "",
    ]
    if not found:
        lines.append("None: no silent error in any repeat.")
        return "\n".join(lines)
    lines += [
        f"{len({(case_id, name) for case_id, name, _ in found})} (case, field) pair(s) "
        f"with a silent error.",
        "",
        "| Case | Field | Expected | Got | Repeats |",
        "|---|---|---|---|---|",
    ]
    order = {case.id: index for index, case in enumerate(run.cases)}
    for case_id, name, got in sorted(found, key=lambda k: (order[k[0]], FIELD_NAMES.index(k[1]))):
        repeats = ", ".join(str(r) for r in found[(case_id, name, got)])
        lines.append(_row([case_id, name, _expected(cases[case_id], name), got, repeats]))
    return "\n".join(lines)


def _case_table(run: FieldRun) -> str:
    lines = [
        "## Cases",
        "",
        "Got shows the first successful repeat. Outcomes list one letter per repeat "
        "(h hit, f flagged miss, S silent wrong) for each field that is not a hit in every "
        "repeat.",
        "",
        "| Case | Deadline phrase | Price phrase | Expected | Got | Outcomes |",
        "|---|---|---|---|---|---|",
    ]
    for case in run.cases:
        observations = [o for o in run.observations if o.case_id == case.id]
        first = next((o for o in observations if o.parsed is not None), None)
        parsed = first.parsed if first else None
        got = _got_summary(parsed, first) if parsed and first else "all calls failed"
        lines.append(
            _row(
                [
                    case.id,
                    (parsed.deadline_text if parsed else None) or NO_VALUE,
                    (parsed.price_text if parsed else None) or NO_VALUE,
                    "; ".join(f"{name}={_expected(case, name)}" for name in FIELD_NAMES),
                    got,
                    _outcomes_label(observations),
                ]
            )
        )
    return "\n".join(lines)


def _got_summary(parsed: ParsedFields, obs: FieldObservation) -> str:
    parts = []
    for name in FIELD_NAMES:
        flag = "!" if name in obs.uncertain else ""
        parts.append(f"{name}={_got(parsed, name)}{flag}")
    return "; ".join(parts)


def _outcomes_label(observations: Sequence[FieldObservation]) -> str:
    scored = sorted((o for o in observations if o.outcomes is not None), key=lambda o: o.repeat)
    failed = sum(o.failure is not None for o in observations)
    parts = []
    for name in FIELD_NAMES:
        letters = "".join(_LETTER[o.outcomes[name]] for o in scored if o.outcomes)
        if letters and set(letters) != {"h"}:
            parts.append(f"{name} {letters}")
    if failed:
        parts.append(f"{failed} failed call(s)")
    if not parts:
        return "all hit" if scored else NO_VALUE
    return "; ".join(parts)


def _unstable(run: FieldRun) -> str:
    lines = ["## Unstable (case, field) pairs", ""]
    rows: list[str] = []
    for case in run.cases:
        scored = sorted(
            (o for o in run.observations if o.case_id == case.id and o.outcomes is not None),
            key=lambda o: o.repeat,
        )
        for name in FIELD_NAMES:
            outcomes = [(o.repeat, o.outcomes[name]) for o in scored if o.outcomes]
            if len({outcome for _, outcome in outcomes}) > 1:
                detail = "; ".join(f"{repeat}: {outcome}" for repeat, outcome in outcomes)
                rows.append(_row([case.id, name, detail]))
    if not rows:
        lines.append("None: every field had the same outcome in all repeats of a case.")
        return "\n".join(lines)
    lines += ["| Case | Field | Outcome by repeat |", "|---|---|---|", *rows]
    return "\n".join(lines)


def _failures(run: FieldRun) -> str:
    lines = ["## Failed extractor calls", ""]
    failed = [o for o in run.observations if o.failure is not None]
    if not failed:
        lines.append("None.")
        return "\n".join(lines)
    lines += [
        "A failed call has no parse: it is counted here, not as a hit or a miss.",
        "",
        "| Case | Repeat | Error |",
        "|---|---|---|",
    ]
    lines += [_row([o.case_id, str(o.repeat), f"`{o.failure}`"]) for o in failed]
    return "\n".join(lines)


def _methodology(run: FieldRun) -> str:
    lines = [
        "## Methodology notes",
        "",
        "- Each call runs the configured extractor on one inquiry, then the real "
        "`build_parsed` (deadline resolution, validation, uncertainty flags) with the Warsaw "
        "day of reception as the reference date. Six fields are scored: customer, product "
        "code, quantity, deadline, substitute allowed and price (kind and value).",
        "- Three outcomes per field. Hit: the value is right (and flagged when the label says "
        "it must be). Flagged miss: wrong or missing but marked uncertain, acceptable under "
        "PRD FR-002. Silent wrong: wrong, or lacking a required flag, and not marked "
        "uncertain: the risk the evaluation measures.",
        "- Oracle policy: every label is derived by hand from the written rules and a "
        "calendar, with the arithmetic in the case rationale. No label comes from running the "
        "parser or the deadline resolver, and loading the cases calls neither.",
        "- Customer matches when the label's words appear as a contiguous run in the parsed "
        "name (the rule that matches customer records); product code ignores case and "
        "surrounding spaces.",
        "- Deadline and price phrases are shown for diagnosis only and are not scored.",
        f"- Each case ran {run.repeats} time(s); this is a measurement, not a gate.",
    ]
    return "\n".join(lines)


# --- Formatting -------------------------------------------------------------------------


def _expected(case: FieldCase, name: FieldName) -> str:
    expected = case.expected
    if name == "price":
        text = _price(expected.price.kind, expected.price.value)
        flagged = expected.price.flagged
    else:
        field = getattr(expected, name)
        text = _scalar(field.value)
        flagged = field.flagged
    return f"{text} (flagged)" if flagged else text


def _got(parsed: ParsedFields, name: FieldName) -> str:
    if name == "price":
        return _price(parsed.price_kind, parsed.price_value)
    return _scalar(getattr(parsed, name))


def _price(kind: str, value: Decimal | None) -> str:
    return kind if value is None else f"{kind} {value.normalize():f}"


def _scalar(value: object) -> str:
    if value is None:
        return NO_VALUE
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ") for cell in cells) + " |"
