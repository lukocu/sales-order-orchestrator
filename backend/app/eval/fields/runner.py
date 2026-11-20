"""Run the extractor over the field cases and score each parse; no database involved.

Each (case, repeat) calls the extractor once, passes the extraction through the real
`build_parsed` with the Warsaw day of reception as the reference date, and scores the six
fields. An `ExtractionError` is kept as a failed observation (class name only: messages and
inquiry text stay out of the report) and never counts as a hit; any other exception
propagates.
"""

import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from app.eval.fields.cases import FieldCase, reference_day
from app.eval.fields.scoring import FIELD_NAMES, CaseRepeats, FieldOutcome, score_case
from app.parsing.analyze import build_parsed
from app.parsing.extractor import ExtractionError, InquiryExtractor
from app.parsing.schema import FieldName, ParsedFields


class FieldObservation(BaseModel):
    """One extractor call: the parse and its outcomes, or the class of the error."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    repeat: int  # 1-based
    duration_ms: int
    failure: str | None = None  # exception class name when the call failed
    outcomes: dict[FieldName, FieldOutcome] | None = None
    parsed: ParsedFields | None = None
    uncertain: list[FieldName] = []
    input_tokens: int | None = None  # None when the extractor reports no usage
    output_tokens: int | None = None


class FieldRun(BaseModel):
    """One pass of the field cases: metadata, the labels as run and every observation."""

    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    finished_at: datetime
    provider: str
    model: str | None  # None for the rule-based parser
    extractor: str
    repeats: int
    cases_sha256: str
    cases: list[FieldCase]  # in run order; kept so the report can be re-read on its own
    observations: list[FieldObservation]

    def scored(self) -> list[CaseRepeats]:
        """Each case with the outcomes of its successful repeats (failed calls are left out)."""
        return [
            (
                case,
                [
                    o.outcomes
                    for o in self.observations
                    if o.case_id == case.id and o.outcomes is not None
                ],
            )
            for case in self.cases
        ]


def run_field_eval(
    cases: Sequence[FieldCase],
    extractor: InquiryExtractor,
    *,
    repeats: int,
    pause_seconds: float,
    provider: str,
    model: str | None,
    cases_version: str,
    sleep: Callable[[float], None] = time.sleep,
) -> FieldRun:
    """Parse every case `repeats` times and score it.

    `pause_seconds` separates consecutive calls (rate limits); there is no sleep when it is 0.
    """
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    started_at = datetime.now(UTC)
    observations: list[FieldObservation] = []
    for repeat in range(1, repeats + 1):
        for case in cases:
            if pause_seconds > 0 and observations:
                sleep(pause_seconds)
            observations.append(_observe(case, repeat, extractor))
    return FieldRun(
        started_at=started_at,
        finished_at=datetime.now(UTC),
        provider=provider,
        model=model,
        extractor=extractor.name,
        repeats=repeats,
        cases_sha256=cases_version,
        cases=list(cases),
        observations=observations,
    )


def _observe(case: FieldCase, repeat: int, extractor: InquiryExtractor) -> FieldObservation:
    reference_date = reference_day(case.received_at)
    started = time.perf_counter()
    try:
        result = extractor.extract(case.subject, case.body, reference_date)
    except ExtractionError as error:
        return FieldObservation(
            case_id=case.id,
            repeat=repeat,
            duration_ms=_elapsed_ms(started),
            failure=type(error).__name__,
        )
    duration_ms = _elapsed_ms(started)
    parsed, uncertain = build_parsed(result.extraction, reference_date)
    usage = result.usage
    return FieldObservation(
        case_id=case.id,
        repeat=repeat,
        duration_ms=duration_ms,
        outcomes=score_case(case, parsed, uncertain),
        parsed=parsed,
        uncertain=[name for name in FIELD_NAMES if name in uncertain],
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
    )


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
