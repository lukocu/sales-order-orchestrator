from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlmodel import Session, col

from app.tracing import LlmUsage, run
from app.tracing.models import TraceRun

TEST_SUBJECT_TYPE = "test"

USAGE = LlmUsage(
    provider="google",
    model="gemini-2.5-flash",
    input_tokens=1200,
    output_tokens=300,
    cache_read_tokens=200,
    raw={"promptTokenCount": 1200, "secret": "should-not-leak"},
)


@pytest.fixture(autouse=True)
def _delete_test_runs(migrated_engine: Engine) -> Iterator[None]:
    yield
    with Session(migrated_engine) as session:
        session.exec(delete(TraceRun).where(col(TraceRun.subject_type) == TEST_SUBJECT_TYPE))
        session.commit()


def _traced_run(engine: Engine) -> int:
    with run(engine, subject_type=TEST_SUBJECT_TYPE, subject_id="api-test") as r:
        with r.step("normalize", kind="deterministic"):
            pass
        with r.step("parse", kind="llm") as s:
            s.record_usage(USAGE)
    assert r.id is not None
    return r.id


def test_run_summary_shape(client: TestClient, migrated_engine: Engine) -> None:
    run_id = _traced_run(migrated_engine)

    response = client.get(f"/api/runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "subject_type",
        "subject_id",
        "status",
        "started_at",
        "duration_ms",
        "steps",
        "totals",
    }
    assert (body["id"], body["subject_type"], body["status"]) == (run_id, "test", "completed")
    assert [step["name"] for step in body["steps"]] == ["normalize", "parse"]
    assert set(body["totals"]) == {
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cost_usd",
        "cost_complete",
        "steps_duration_ms",
        "duration_ms",
    }
    assert body["totals"]["input_tokens"] == 1200
    assert body["totals"]["cost_complete"] is True


def test_decimal_cost_is_a_string(client: TestClient, migrated_engine: Engine) -> None:
    run_id = _traced_run(migrated_engine)

    body = client.get(f"/api/runs/{run_id}").json()

    step_cost = body["steps"][1]["cost_usd"]
    assert isinstance(step_cost, str)
    assert isinstance(body["totals"]["cost_usd"], str)
    assert Decimal(body["totals"]["cost_usd"]) == Decimal(step_cost) > 0
    assert body["steps"][0]["cost_usd"] is None


def test_response_has_no_raw_usage(client: TestClient, migrated_engine: Engine) -> None:
    run_id = _traced_run(migrated_engine)

    response = client.get(f"/api/runs/{run_id}")

    assert "raw_usage" not in response.text
    assert "should-not-leak" not in response.text


def test_unknown_run_is_json_404(client: TestClient) -> None:
    response = client.get("/api/runs/999999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Run not found"}
