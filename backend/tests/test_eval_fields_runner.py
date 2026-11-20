"""The field eval runner with a scripted extractor: outcomes, failures, repeats, pauses."""

from datetime import date
from typing import Any

import pytest

from app.eval.fields.cases import FieldCase, load_cases
from app.eval.fields.runner import FieldRun, run_field_eval
from app.parsing.extractor import ExtractionFailed, ExtractionResult
from app.parsing.fake import RuleBasedExtractor
from app.parsing.schema import ModelExtraction
from app.tracing.models import StepKind
from app.tracing.pricing import LlmUsage


def make_case(case_id: str, **expected: Any) -> FieldCase:
    """A Monday-2026-11-02 inquiry whose subject is its id, so the stub can tell cases apart."""
    fields: dict[str, Any] = {
        "customer": {"value": "ACME"},
        "product_code": {"value": "ABC-200"},
        "quantity": {"value": 80},
        "deadline": {"value": "2026-11-06", "weekday": "friday"},
        "substitute_allowed": {"value": True},
        "price": {"kind": "none"},
    }
    return FieldCase.model_validate(
        {
            "id": case_id,
            "subject": case_id,
            "body": "Prosimy o oferte.",
            "received_at": "2026-11-02T09:00:00+01:00",
            "expected": fields | expected,
            "rationale": "Monday 2026-11-02 plus four days is Friday 2026-11-06.",
            "tags": ["deadline_supported"],
        }
    )


def extraction(**update: Any) -> ModelExtraction:
    """The correct reading of `make_case`, with some fields replaced."""
    fields: dict[str, Any] = {
        "customer": "ACME Sp. z o.o.",
        "product_code": "ABC-200",
        "quantity": 80,
        "deadline_text": "do piątku",
        "deadline_date": "2026-11-06",
        "substitute_allowed": True,
        "price_kind": "none",
        "price_value": None,
        "price_text": None,
        "uncertain": [],
    }
    return ModelExtraction.model_validate(fields | update)


USAGE = LlmUsage(provider="openai", model="m", input_tokens=120, output_tokens=30)


class ScriptedExtractor:
    """Answers each call from a per-case script (the case id is the subject), in order."""

    name = "scripted"
    step_kind: StepKind = "llm"

    def __init__(self, script: dict[str, list[ModelExtraction | Exception]]) -> None:
        self.script = {case_id: list(items) for case_id, items in script.items()}
        self.calls: list[tuple[str, date]] = []
        self.usage: LlmUsage | None = None

    def extract(self, subject: str, body: str, reference_date: date) -> ExtractionResult:
        self.calls.append((subject, reference_date))
        item = self.script[subject].pop(0)
        if isinstance(item, Exception):
            raise item
        return ExtractionResult(extraction=item, usage=self.usage)


def run(
    cases: list[FieldCase],
    extractor: ScriptedExtractor,
    *,
    repeats: int = 1,
    pause_seconds: float = 0,
    sleeps: list[float] | None = None,
) -> FieldRun:
    return run_field_eval(
        cases,
        extractor,
        repeats=repeats,
        pause_seconds=pause_seconds,
        provider="groq",
        model="test-model",
        cases_version="abc123",
        sleep=sleeps.append if sleeps is not None else (lambda seconds: None),
    )


def test_correct_extraction_is_all_hits_and_keeps_the_parse() -> None:
    extractor = ScriptedExtractor({"a": [extraction()]})

    result = run([make_case("a")], extractor)

    (obs,) = result.observations
    assert obs.outcomes is not None
    assert set(obs.outcomes.values()) == {"hit"}
    assert obs.parsed is not None
    assert obs.parsed.deadline == date(2026, 11, 6)
    assert obs.parsed.deadline_text == "do piątku"
    assert obs.uncertain == []
    assert obs.failure is None
    assert obs.duration_ms >= 0
    assert (result.provider, result.model, result.extractor) == ("groq", "test-model", "scripted")
    assert result.cases_sha256 == "abc123"
    assert result.repeats == 1
    assert result.started_at <= result.finished_at


def test_reference_date_is_the_warsaw_day_of_reception() -> None:
    late_evening = FieldCase.model_validate(
        make_case("a").model_dump(mode="json") | {"received_at": "2026-11-02T23:30:00-05:00"}
    )
    extractor = ScriptedExtractor({"a": [extraction()]})

    run([late_evening], extractor)

    # 23:30 at UTC-5 is 05:30 on the 3rd in Warsaw.
    assert extractor.calls == [("a", date(2026, 11, 3))]


def test_silent_wrong_and_flagged_miss_are_told_apart() -> None:
    extractor = ScriptedExtractor({"a": [extraction(quantity=81, customer=None)]})

    (obs,) = run([make_case("a")], extractor).observations

    assert obs.outcomes is not None
    assert obs.outcomes["quantity"] == "silent_wrong"  # wrong and not marked
    assert obs.outcomes["customer"] == "flagged_miss"  # empty is always flagged "Missing"
    assert obs.outcomes["deadline"] == "hit"
    assert obs.uncertain == ["customer"]


def test_failed_call_is_recorded_by_class_and_is_never_a_hit() -> None:
    error = ExtractionFailed("timeout for Prosimy o oferte")
    extractor = ScriptedExtractor({"a": [error], "b": [extraction()]})

    result = run([make_case("a"), make_case("b")], extractor)

    failed, ok = result.observations
    assert failed.failure == "ExtractionFailed"
    assert failed.outcomes is None
    assert failed.parsed is None
    assert ok.failure is None
    assert "timeout" not in result.model_dump_json()  # the message is never kept
    # Scoring counts the successful call only; the failed one is neither hit nor miss.
    (_, failed_repeats), (_, ok_repeats) = result.scored()
    assert failed_repeats == []
    assert len(ok_repeats) == 1


def test_other_exceptions_propagate() -> None:
    extractor = ScriptedExtractor({"a": [RuntimeError("bug")]})

    with pytest.raises(RuntimeError):
        run([make_case("a")], extractor)


def test_every_case_runs_once_per_repeat() -> None:
    extractor = ScriptedExtractor(
        {
            "a": [extraction(), extraction(quantity=81), extraction()],
            "b": [extraction(), extraction(), extraction()],
        }
    )

    result = run([make_case("a"), make_case("b")], extractor, repeats=3)

    assert len(extractor.calls) == 6
    assert sorted((o.case_id, o.repeat) for o in result.observations) == [
        (case_id, repeat) for case_id in ("a", "b") for repeat in (1, 2, 3)
    ]
    case_a = [o for o in result.observations if o.case_id == "a"]
    assert [
        o.outcomes["quantity"] for o in sorted(case_a, key=lambda o: o.repeat) if o.outcomes
    ] == [
        "hit",
        "silent_wrong",
        "hit",
    ]
    assert result.repeats == 3


def test_token_usage_is_kept_when_the_extractor_reports_it() -> None:
    extractor = ScriptedExtractor({"a": [extraction(), extraction()]})
    extractor.usage = USAGE

    with_usage = run([make_case("a")], extractor).observations[0]
    extractor.usage = None
    without = run([make_case("a")], extractor).observations[0]

    assert (with_usage.input_tokens, with_usage.output_tokens) == (120, 30)
    assert (without.input_tokens, without.output_tokens) == (None, None)


def test_pause_separates_calls_and_is_skipped_at_zero() -> None:
    script: dict[str, list[ModelExtraction | Exception]] = {
        "a": [extraction(), extraction()],
        "b": [extraction(), extraction()],
    }
    cases = [make_case("a"), make_case("b")]

    paused: list[float] = []
    run(cases, ScriptedExtractor(script), repeats=2, pause_seconds=0.5, sleeps=paused)
    script_again: dict[str, list[ModelExtraction | Exception]] = {
        "a": [extraction(), extraction()],
        "b": [extraction(), extraction()],
    }
    unpaused: list[float] = []
    run(cases, ScriptedExtractor(script_again), repeats=2, pause_seconds=0, sleeps=unpaused)

    assert paused == [0.5, 0.5, 0.5]  # four calls, three gaps
    assert unpaused == []


def test_repeats_must_be_positive() -> None:
    with pytest.raises(ValueError):
        run([make_case("a")], ScriptedExtractor({}), repeats=0)


def test_run_survives_a_json_round_trip() -> None:
    extractor = ScriptedExtractor({"a": [extraction(price_kind="target_price", price_value=12.5)]})
    result = run([make_case("a")], extractor)

    assert FieldRun.model_validate_json(result.model_dump_json()) == result


def test_regex_extractor_runs_over_the_whole_built_in_set() -> None:
    cases = load_cases()

    result = run_field_eval(
        cases,
        RuleBasedExtractor(),
        repeats=1,
        pause_seconds=0,
        provider="fake",
        model=None,
        cases_version="x",
    )

    assert len(result.observations) == len(cases)
    assert all(o.outcomes is not None for o in result.observations)
