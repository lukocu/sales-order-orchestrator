"""Compare the fixed workflow with the orchestrator on the labelled set.

    python -m app.eval --repeats 3
    docker compose run --rm backend uv run python -m app.eval --repeats 3
    docker compose run --rm backend uv run python -m app.eval --allow-fake --repeats 1

The `workflow` arm plans with the rule-based planner; the `orchestrator` arm and the shared
recommender come from the settings (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`). Without
`--allow-fake` the command refuses to run when no LLM provider is configured, because the
orchestrator would silently be the rule-based planner. Runs only against the local database:
it writes and then deletes temporary `[eval] ` inquiries. LLM failures are part of the result,
so the exit code is 0 even when some runs failed.
"""

import argparse
import logging
import sys
from pathlib import Path

from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.db import get_engine
from app.eval.cases import CASES_PATH, load_cases
from app.eval.runner import Arm, cases_sha256, run_eval
from app.eval.scoring import summarize
from app.llm.client import DEFAULT_MODELS
from app.orchestration.planning import RuleBasedPlanner, get_planner
from app.recommendation.recommender import get_recommender
from app.settings import get_settings

logger = logging.getLogger("app.eval")

SETUP_USERNAME = "sales"


def _repeats(value: str) -> int:
    repeats = int(value)
    if repeats < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return repeats


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval",
        description="Compare the fixed workflow with the orchestrator on the labelled set.",
    )
    parser.add_argument("--repeats", type=_repeats, default=3, help="runs per case and arm")
    parser.add_argument("--pause-seconds", type=float, default=2.0, help="pause between arm calls")
    parser.add_argument("--cases", type=Path, default=CASES_PATH, help="case file (JSON)")
    parser.add_argument("--only", nargs="+", metavar="CASE_ID", help="run only these cases")
    parser.add_argument("--out", type=Path, default=Path("eval_reports"), help="report directory")
    parser.add_argument(
        "--allow-fake",
        action="store_true",
        help="run without an LLM provider (both arms plan with rules; for tests)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parser().parse_args(argv)
    settings = get_settings()

    if not args.allow_fake and (settings.llm_provider == "fake" or settings.llm_api_key is None):
        logger.error(
            "No LLM provider is configured, so the orchestrator arm would not call an LLM. "
            "Set LLM_PROVIDER (groq or openrouter) and LLM_API_KEY in .env, "
            "or pass --allow-fake for a run on the rule-based fakes."
        )
        return 2

    cases = load_cases(args.cases)
    if args.only:
        unknown = sorted(set(args.only) - {case.id for case in cases})
        if unknown:
            logger.error("Unknown case ids: %s", ", ".join(unknown))
            return 2
        cases = [case for case in cases if case.id in args.only]

    engine = get_engine()
    with Session(engine) as session:
        user = session.exec(select(User).where(col(User.username) == SETUP_USERNAME)).first()
        if user is None:
            logger.error(
                "Demo account %s does not exist; run the migrations first.", SETUP_USERNAME
            )
            return 1
        setup_user = AuthUser.from_user(user)

    provider = settings.llm_provider
    model = None if provider == "fake" else settings.llm_model or DEFAULT_MODELS[provider]
    eval_run = run_eval(
        engine,
        cases,
        [
            Arm(name="workflow", planner=RuleBasedPlanner()),
            Arm(name="orchestrator", planner=get_planner(settings)),
        ],
        get_recommender(settings),
        repeats=args.repeats,
        pause_seconds=args.pause_seconds,
        user=setup_user,
        provider=provider,
        model=model,
        cases_version=cases_sha256(args.cases),
    )

    for case_id, reason in eval_run.setup_errors:
        logger.warning("Setup error · %s: %s", case_id, reason)
    for arm in ("workflow", "orchestrator"):
        arm_runs = [r for r in eval_run.runs if r.arm == arm]
        if not arm_runs:
            logger.info("%s: no runs", arm)
            continue
        summary = summarize(arm_runs)
        logger.info(
            "%s: full %d/%d · option %d/%d · policy %d/%d · failures %s · "
            "cost %s USD (complete: %s) · mean %.0f ms",
            arm,
            summary.full.hits,
            summary.full.total,
            summary.option.hits,
            summary.option.total,
            summary.policy.hits,
            summary.policy.total,
            summary.failures or "none",
            summary.cost_usd_total,
            summary.cost_complete,
            summary.duration_ms_mean,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
