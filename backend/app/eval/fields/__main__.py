"""Measure how well the inquiry parser reads each field on the hand-labelled set.

    python -m app.eval.fields --repeats 3
    docker compose run --rm backend uv run python -m app.eval.fields --repeats 3
    docker compose run --rm -e LLM_PROVIDER=fake backend uv run python -m app.eval.fields \
        --allow-fake --repeats 1

The extractor comes from the settings (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`). Without
`--allow-fake` the command refuses to run when no LLM provider is configured, because the
regex parser would be measured instead of the model. No database is used. The report goes to
`--out` as Markdown and JSON. Failed extractor calls are part of the result, so the exit code
is 0 even when some calls failed; an unknown `--only` id or a missing provider exits with 2.
"""

import argparse
import logging
import sys
from pathlib import Path

from app.eval.fields.cases import FIELD_CASES_PATH, load_cases
from app.eval.fields.report import write_report
from app.eval.fields.runner import run_field_eval
from app.eval.fields.scoring import FIELD_NAMES, summarize
from app.eval.runner import cases_sha256
from app.llm.client import DEFAULT_MODELS
from app.parsing.extractor import get_extractor
from app.settings import get_settings

logger = logging.getLogger("app.eval.fields")


def _repeats(value: str) -> int:
    repeats = int(value)
    if repeats < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return repeats


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.fields",
        description="Measure how well the inquiry parser reads each field on the labelled set.",
    )
    parser.add_argument("--repeats", type=_repeats, default=3, help="runs per case")
    parser.add_argument("--pause-seconds", type=float, default=1.0, help="pause between calls")
    parser.add_argument(
        "--cases", type=Path, default=FIELD_CASES_PATH, help="field case file (JSON)"
    )
    parser.add_argument("--only", nargs="+", metavar="CASE_ID", help="run only these cases")
    parser.add_argument(
        "--out", type=Path, default=Path("eval_reports/fields"), help="report directory"
    )
    parser.add_argument(
        "--allow-fake",
        action="store_true",
        help="run without an LLM provider (the extractor is whatever LLM_PROVIDER selects)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parser().parse_args(argv)
    settings = get_settings()

    if not args.allow_fake and (settings.llm_provider == "fake" or settings.llm_api_key is None):
        logger.error(
            "No LLM provider is configured, so the regex parser would be measured instead of "
            "the model. Set LLM_PROVIDER (groq or openrouter) and LLM_API_KEY in .env, "
            "or pass --allow-fake for a run on the rule-based fake."
        )
        return 2

    cases = load_cases(args.cases)
    if args.only:
        unknown = sorted(set(args.only) - {case.id for case in cases})
        if unknown:
            logger.error("Unknown case ids: %s", ", ".join(unknown))
            return 2
        cases = [case for case in cases if case.id in args.only]

    provider = settings.llm_provider
    model = None if provider == "fake" else settings.llm_model or DEFAULT_MODELS[provider]
    field_run = run_field_eval(
        cases,
        get_extractor(settings),
        repeats=args.repeats,
        pause_seconds=args.pause_seconds,
        provider=provider,
        model=model,
        cases_version=cases_sha256(args.cases),
    )

    summary = summarize(field_run.scored())
    for name in FIELD_NAMES:
        tally = summary.per_field[name]
        logger.info(
            "%s: hit %d/%d · flagged miss %d · silent wrong %d",
            name,
            tally.hits,
            tally.total,
            tally.flagged_misses,
            tally.silent_wrongs,
        )
    failed = sum(o.failure is not None for o in field_run.observations)
    if failed:
        logger.warning("%d of %d extractor calls failed", failed, len(field_run.observations))

    md_path, json_path = write_report(field_run, args.out)
    logger.info("Report written to %s and %s", md_path, json_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
