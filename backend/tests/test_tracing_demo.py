from decimal import Decimal

from sqlalchemy import Engine, delete
from sqlmodel import Session, col

from app.tracing import price_usage
from app.tracing.demo import DEMO_SUBJECT_TYPE, PRICED_USAGE, UNPRICED_USAGE, create_demo_run
from app.tracing.models import TraceRun
from app.tracing.summary import get_run_summary


def test_demo_priced_model_has_a_list_price() -> None:
    price = price_usage(PRICED_USAGE)

    assert price.status == "priced"
    assert price.cost_usd is not None
    assert price.cost_usd > Decimal(0)


def test_demo_free_model_is_unpriced() -> None:
    assert price_usage(UNPRICED_USAGE).status == "unpriced"


def test_demo_run_shows_all_three_price_states(migrated_engine: Engine) -> None:
    run_id = create_demo_run(migrated_engine)
    assert run_id is not None
    try:
        with Session(migrated_engine) as session:
            summary = get_run_summary(session, run_id)

        assert summary is not None
        assert summary.subject_type == DEMO_SUBJECT_TYPE
        assert summary.status == "completed"
        assert [step.price_status for step in summary.steps] == [
            "not_applicable",
            "priced",
            "unpriced",
        ]
        assert summary.totals.cost_complete is False
        assert summary.totals.cost_usd > Decimal(0)
    finally:
        with Session(migrated_engine) as session:
            session.exec(delete(TraceRun).where(col(TraceRun.id) == run_id))
            session.commit()
