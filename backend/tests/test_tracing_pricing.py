import importlib.metadata
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.tracing.pricing import LlmUsage, price_usage

# Present in the genai-prices bundled snapshot (checked against 0.2.1).
PRICED_PROVIDER = "google"
PRICED_MODEL = "gemini-2.5-flash"


def _usage(**overrides: object) -> LlmUsage:
    fields: dict[str, object] = {
        "provider": PRICED_PROVIDER,
        "model": PRICED_MODEL,
        "input_tokens": 1000,
        "output_tokens": 500,
    }
    fields.update(overrides)
    return LlmUsage.model_validate(fields)


def test_known_model_is_priced_as_positive_decimal() -> None:
    result = price_usage(_usage(cache_read_tokens=100))

    assert result.status == "priced"
    assert isinstance(result.cost_usd, Decimal)
    assert result.cost_usd > 0


def test_source_names_genai_prices_version() -> None:
    result = price_usage(_usage())

    assert result.source == f"genai-prices {importlib.metadata.version('genai-prices')}"


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        (PRICED_PROVIDER, "definitely-not-a-real-model-xyz"),
        ("definitely-not-a-provider", PRICED_MODEL),
    ],
)
def test_unknown_model_or_provider_is_unpriced(provider: str, model: str) -> None:
    result = price_usage(_usage(provider=provider, model=model))

    assert result.status == "unpriced"
    assert result.cost_usd is None
    assert result.source is None


@pytest.mark.parametrize(
    "field", ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]
)
def test_negative_token_counts_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        _usage(**{field: -1})


def test_inconsistent_usage_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        price_usage(_usage(input_tokens=10, cache_read_tokens=50))


def test_separately_priced_calls_sum_exactly() -> None:
    first = price_usage(_usage(input_tokens=1234, output_tokens=56))
    second = price_usage(_usage(input_tokens=789, output_tokens=1011, cache_read_tokens=300))
    assert first.cost_usd is not None
    assert second.cost_usd is not None

    total = first.cost_usd + second.cost_usd

    # Decimal arithmetic is exact: no float rounding creeps into aggregated costs.
    assert isinstance(total, Decimal)
    assert total - first.cost_usd == second.cost_usd
    assert total - second.cost_usd == first.cost_usd
