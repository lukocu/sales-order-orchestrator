"""Normalized LLM usage and its list-price cost via the bundled `genai-prices` data."""

import importlib.metadata
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from genai_prices import Usage, calc_price
from pydantic import BaseModel, ConfigDict, Field

PricedStatus = Literal["priced", "unpriced"]


class LlmUsage(BaseModel):
    """Usage of one model call, normalized across providers."""

    model_config = ConfigDict(frozen=True)

    provider: str  # genai-prices provider id, e.g. google, openai, anthropic, openrouter
    model: str
    input_tokens: int = Field(ge=0)  # includes cache_read_tokens and cache_write_tokens
    output_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    raw: dict[str, Any] | None = None  # provider's original usage payload


@dataclass(frozen=True)
class PriceResult:
    cost_usd: Decimal | None
    status: PricedStatus
    source: str | None


def price_usage(usage: LlmUsage) -> PriceResult:
    """Price one call. An unknown model or provider yields `unpriced` instead of failing.

    `ValueError` (inconsistent usage, e.g. cache tokens above input tokens) propagates:
    it is a programming error in the caller's usage mapping.
    """
    try:
        calculation = calc_price(
            Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
            ),
            usage.model,
            provider_id=usage.provider,
        )
    except LookupError:
        return PriceResult(None, "unpriced", None)
    return PriceResult(calculation.total_price, "priced", _price_source())


def _price_source() -> str:
    return f"genai-prices {importlib.metadata.version('genai-prices')}"
