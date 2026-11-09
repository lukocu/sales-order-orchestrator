"""Step and cost tracing: persisted runs and their steps.

Domain code wraps its work in a run and each unit of work in a step; the recorder measures
time, prices model usage and writes the rows, also when the body raises::

    from app.tracing import LlmUsage, run

    with run(engine, subject_type="inquiry", subject_id=str(inquiry.id)) as r:
        with r.step("normalize", kind="deterministic"):
            text = normalize(inquiry.body)
        with r.step("parse", kind="llm") as s:
            response = client.generate(text)
            s.record_usage(
                LlmUsage(
                    provider="google",
                    model=response.model,
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    raw=response.usage.model_dump(),
                )
            )
"""

from app.tracing.pricing import LlmUsage, PriceResult, price_usage
from app.tracing.recorder import RunHandle, StepRecorder, run

__all__ = ["LlmUsage", "PriceResult", "RunHandle", "StepRecorder", "price_usage", "run"]
