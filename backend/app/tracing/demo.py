"""Create a demo run showing all three price states, without calling any LLM.

    python -m app.tracing.demo
    docker compose run --rm backend uv run python -m app.tracing.demo
    docker compose run --rm -e DATABASE_URL=<Supabase session pooler> backend \
        uv run python -m app.tracing.demo

The token counts are fixed; the cost comes from the bundled `genai-prices` data.
"""

import logging
import sys
from uuid import uuid4

from sqlalchemy import Engine

from app.db import get_engine
from app.tracing.pricing import LlmUsage
from app.tracing.recorder import run

DEMO_SUBJECT_TYPE = "demo"
DEMO_INQUIRY = "  Please quote   2 pallets of A4 paper  "

# Priced by genai-prices 0.2.1 at a non-zero list price.
PRICED_USAGE = LlmUsage(
    provider="google",
    model="gemini-2.5-flash",
    input_tokens=1200,
    output_tokens=300,
    cache_read_tokens=200,
    raw={"promptTokenCount": 1200, "candidatesTokenCount": 300, "cachedContentTokenCount": 200},
)

# A free OpenRouter model missing from the genai-prices 0.2.1 data, so the step is `unpriced`.
UNPRICED_USAGE = LlmUsage(
    provider="openrouter",
    model="z-ai/glm-4.5-air:free",
    input_tokens=800,
    output_tokens=150,
    raw={"prompt_tokens": 800, "completion_tokens": 150},
)


def create_demo_run(engine: Engine) -> int | None:
    """Write the demo run; returns its id, or None when the run could not be saved."""
    with run(engine, subject_type=DEMO_SUBJECT_TYPE, subject_id=f"demo-{uuid4()}") as r:
        with r.step("normalize", kind="deterministic"):
            " ".join(DEMO_INQUIRY.split())
        with r.step("parse", kind="llm") as s:
            s.record_usage(PRICED_USAGE)
        with r.step("draft-reply", kind="llm") as s:
            s.record_usage(UNPRICED_USAGE)
    return r.id


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_id = create_demo_run(get_engine())
    if run_id is None:
        print("Demo run could not be saved; see the errors above.", file=sys.stderr)
        return 1
    print(f"Demo run id: {run_id}")
    print(f"GET /api/runs/{run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
