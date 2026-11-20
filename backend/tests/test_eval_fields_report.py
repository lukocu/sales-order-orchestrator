"""The field eval report and CLI: file names, sections, silent errors, exit codes. No database."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import app.db
from app.eval.fields import __main__ as cli
from app.eval.fields.report import _row, render_markdown, write_report
from app.eval.fields.runner import FieldRun, FieldRunAborted
from app.parsing.extractor import ExtractionFailed
from app.settings import get_settings
from tests.test_eval_fields_runner import USAGE, ScriptedExtractor, extraction, make_case, run

SECTIONS = [
    "# Parser field evaluation",
    "## Accuracy per field",
    "## SILENT ERRORS",
    "## Accuracy per tag",
    "## Cases",
    "## Unstable (case, field) pairs",
    "## Failed extractor calls",
    "## Methodology notes",
]


NL = "\n## "  # the start of the next section


def _clean_run() -> FieldRun:
    extractor = ScriptedExtractor({"case-a": [extraction()]})
    return run([make_case("case-a")], extractor)


def _messy_run() -> FieldRun:
    extractor = ScriptedExtractor(
        {
            "case-a": [extraction(quantity=81), extraction(), extraction(quantity=81)],
            "case-b": [ExtractionFailed("SENTINEL-boom"), extraction(), extraction()],
        }
    )
    return run([make_case("case-a"), make_case("case-b")], extractor, repeats=3)


def _json_text(result: FieldRun) -> str:
    return result.model_dump_json()


def test_files_are_named_by_date_provider_and_model(tmp_path: Path) -> None:
    started = datetime(2026, 11, 20, 14, 5, 9, tzinfo=UTC)
    result = _clean_run().model_copy(update={"started_at": started, "model": "Org/Model:Free"})

    md_path, json_path = write_report(result, tmp_path / "nested")

    assert md_path.name == "2026-11-20-groq-org-model-free.md"
    assert json_path.name == "2026-11-20-groq-org-model-free.json"
    assert md_path.read_text(encoding="utf-8").startswith("# Parser field evaluation")


def test_fake_provider_is_named_none(tmp_path: Path) -> None:
    result = _clean_run().model_copy(update={"provider": "fake", "model": None})

    md_path, _ = write_report(result, tmp_path)

    assert md_path.name.endswith("-fake-none.md")


def test_taken_name_gets_the_start_time_suffix(tmp_path: Path) -> None:
    started = datetime(2026, 11, 20, 14, 5, 9, tzinfo=UTC)
    result = _clean_run().model_copy(update={"started_at": started})

    first, _ = write_report(result, tmp_path)
    second, second_json = write_report(result, tmp_path)
    third, _ = write_report(result, tmp_path)

    assert first.name == "2026-11-20-groq-test-model.md"
    assert second.name == "2026-11-20-groq-test-model-140509.md"
    assert second_json.name == "2026-11-20-groq-test-model-140509.json"
    assert third.name == "2026-11-20-groq-test-model-140509-2.md"


def test_every_section_is_present_in_order() -> None:
    text = render_markdown(_messy_run())

    positions = [text.index(section) for section in SECTIONS]

    assert positions == sorted(positions)
    # Silent errors come right after the per-field table, before the tag table.
    assert text.index("## SILENT ERRORS") < text.index("## Accuracy per tag")


def test_silent_errors_list_case_field_values_and_repeats() -> None:
    text = render_markdown(_messy_run())

    silent = text.split("## SILENT ERRORS")[1].split("\n## ")[0]
    assert "case-a" in silent
    assert "quantity" in silent
    assert "| 80 | 81 | 1, 3 |" in silent
    assert "case-b" not in silent  # its failed call is not a silent error


def test_silent_errors_say_none_when_empty() -> None:
    text = render_markdown(_clean_run())

    silent = text.split("## SILENT ERRORS")[1].split("\n## ")[0]
    assert "None" in silent
    assert "case-a" not in silent


def test_unstable_pairs_and_failed_calls_are_listed() -> None:
    text = render_markdown(_messy_run())

    unstable = text.split("## Unstable (case, field) pairs")[1].split("\n## ")[0]
    assert "case-a | quantity | 1: silent_wrong; 2: hit; 3: silent_wrong" in unstable
    failures = text.split("## Failed extractor calls")[1].split("\n## ")[0]
    assert "| case-b | 1 | `ExtractionFailed` |" in failures
    assert "SENTINEL-boom" not in text
    assert "SENTINEL-boom" not in _json_text(_messy_run())


def test_failed_calls_and_unstable_say_none_when_empty() -> None:
    text = render_markdown(_clean_run())

    assert (
        text.split("## Unstable (case, field) pairs")[1]
        .split("\n## ")[0]
        .strip()
        .startswith("None")
    )
    assert text.split("## Failed extractor calls")[1].split("\n## ")[0].strip() == "None."


def test_per_field_table_counts_outcomes() -> None:
    text = render_markdown(_messy_run())

    per_field = text.split("## Accuracy per field")[1].split("\n## ")[0]
    # 5 successful calls: quantity is silent wrong in 2 of them.
    assert "| quantity | 3 (60%) | 0 (0%) | 2 (40%) | 5 |" in per_field
    tags = text.split("## Accuracy per tag")[1].split("\n## ")[0]
    assert "| deadline_supported | 5 (100%) | 0 (0%) | 0 (0%) | 5 |" in tags


def test_json_holds_the_whole_run_and_round_trips(tmp_path: Path) -> None:
    result = _messy_run()

    _, json_path = write_report(result, tmp_path)

    assert FieldRun.model_validate_json(json_path.read_text(encoding="utf-8")) == result
    assert len(json.loads(json_path.read_text(encoding="utf-8"))["observations"]) == 6


def test_a_run_where_every_call_failed_still_renders() -> None:
    extractor = ScriptedExtractor({"case-a": [ExtractionFailed("x"), ExtractionFailed("y")]})
    result = run([make_case("case-a")], extractor, repeats=2)

    text = render_markdown(result)

    assert "all calls failed" in text
    per_field = text.split("## Accuracy per field")[1].split(NL)[0]
    assert "| quantity | 0 | 0 | 0 | 0 |" in per_field  # a zero total prints plain counts
    tags = text.split("## Accuracy per tag")[1].split(NL)[0]
    assert "| deadline_supported | 0 | 0 | 0 | 0 |" in tags  # the tag does not vanish
    assert "| case-a | 1 | `ExtractionFailed` |" in text


def test_a_silent_error_that_only_lacks_the_flag_says_so() -> None:
    case = make_case("case-a", deadline={"value": None, "flagged": True})
    extractor = ScriptedExtractor({"case-a": [extraction(deadline_text=None, deadline_date=None)]})

    text = render_markdown(run([case], extractor))

    silent = text.split("## SILENT ERRORS")[1].split(NL)[0]
    assert "| case-a | deadline | — (flagged) | — (not flagged) | 1 |" in silent


def test_a_partial_run_is_marked_in_the_report() -> None:
    extractor = ScriptedExtractor({"case-a": [extraction()], "case-b": [RuntimeError("bug")]})
    with pytest.raises(FieldRunAborted) as raised:
        run([make_case("case-a"), make_case("case-b")], extractor, repeats=2)

    text = render_markdown(raised.value.run)

    assert "PARTIAL RUN" in text
    assert "`RuntimeError` after 1 of 4 planned calls" in text
    assert "PARTIAL RUN" not in render_markdown(_clean_run())


def test_failed_calls_keep_their_billed_tokens_in_the_totals() -> None:
    extractor = ScriptedExtractor({"a": [extraction()], "b": [ExtractionFailed("x", usage=USAGE)]})
    extractor.usage = USAGE

    text = render_markdown(run([make_case("a"), make_case("b")], extractor))

    assert "Tokens (in / out): 240 / 60" in text


def test_table_cells_cannot_break_out_of_their_row() -> None:
    row = _row(["a|b", "line1\r\nline2", "ends with \\", "plain"])

    assert row == "| a\\|b | line1 line2 | ends with \\\\ | plain |"


# --- CLI --------------------------------------------------------------------------------


@pytest.fixture
def no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("the field eval must not touch the database")

    monkeypatch.setattr(app.db, "get_engine", fail)
    monkeypatch.setattr(app.db, "build_engine", fail)


def _settings(monkeypatch: pytest.MonkeyPatch, **update: object) -> None:
    settings = get_settings().model_copy(update=update)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)


def test_fake_provider_without_allow_fake_exits_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_database: None
) -> None:
    _settings(monkeypatch, llm_provider="fake", llm_api_key=None)

    assert cli.main(["--out", str(tmp_path)]) == 2
    assert list(tmp_path.iterdir()) == []


def test_provider_without_key_and_without_allow_fake_exits_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_database: None
) -> None:
    _settings(monkeypatch, llm_provider="groq", llm_api_key=None)

    assert cli.main(["--out", str(tmp_path)]) == 2


def test_unknown_case_id_exits_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_database: None
) -> None:
    _settings(monkeypatch, llm_provider="fake", llm_api_key=None)

    assert cli.main(["--allow-fake", "--only", "no-such-case", "--out", str(tmp_path)]) == 2
    assert list(tmp_path.iterdir()) == []


def test_allow_fake_run_writes_both_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_database: None
) -> None:
    _settings(monkeypatch, llm_provider="fake", llm_api_key=None)

    code = cli.main(
        [
            "--allow-fake",
            "--repeats",
            "2",
            "--pause-seconds",
            "0",
            "--only",
            "dl-do-piatku",
            "--out",
            str(tmp_path),
        ]
    )

    assert code == 0
    written = sorted(path.suffix for path in tmp_path.iterdir())
    assert written == [".json", ".md"]
    (json_path,) = tmp_path.glob("*.json")
    saved = FieldRun.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert [case.id for case in saved.cases] == ["dl-do-piatku"]
    assert len(saved.observations) == 2
    assert saved.provider == "fake"
    assert saved.model is None


def test_failed_calls_still_exit_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_database: None
) -> None:
    # A provider without a key under --allow-fake: every call fails, the run still reports.
    _settings(monkeypatch, llm_provider="groq", llm_api_key=None)

    code = cli.main(
        ["--allow-fake", "--repeats", "1", "--pause-seconds", "0", "--only", "dl-do-piatku"]
        + ["--out", str(tmp_path)]
    )

    assert code == 0
    (json_path,) = tmp_path.glob("*.json")
    saved = FieldRun.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert [o.failure for o in saved.observations] == ["ExtractionNotConfigured"]


@pytest.mark.parametrize("value", ["inf", "nan", "-1"])
def test_pause_seconds_must_be_finite_and_not_negative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_database: None, value: str
) -> None:
    _settings(monkeypatch, llm_provider="fake", llm_api_key=None)

    with pytest.raises(SystemExit) as raised:
        cli.main(["--allow-fake", "--pause-seconds", value, "--out", str(tmp_path)])

    assert raised.value.code == 2


def test_a_crash_writes_a_partial_report_and_still_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_database: None
) -> None:
    class Crashing:
        name = "crashing"
        step_kind = "llm"

        def extract(self, subject: str, body: str, reference_date: object) -> object:
            raise RuntimeError("bug")

    _settings(monkeypatch, llm_provider="fake", llm_api_key=None)
    monkeypatch.setattr(cli, "get_extractor", lambda settings: Crashing())

    with pytest.raises(RuntimeError, match="bug"):
        cli.main(
            ["--allow-fake", "--pause-seconds", "0", "--only", "dl-do-piatku"]
            + ["--out", str(tmp_path)]
        )

    (json_path,) = tmp_path.glob("*.json")
    saved = FieldRun.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert saved.aborted_by == "RuntimeError"
    assert saved.observations == []
    assert "PARTIAL RUN" in next(tmp_path.glob("*.md")).read_text(encoding="utf-8")
