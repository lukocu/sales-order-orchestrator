"""Extractor interface, its errors and the choice of implementation from settings."""

import datetime as dt
from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends

from app.parsing.schema import ModelExtraction
from app.settings import LlmProvider, Settings, get_settings
from app.tracing.models import StepKind
from app.tracing.pricing import LlmUsage

# Model ids as genai-prices knows them: without the `openai/` prefix Groq is unpriced.
DEFAULT_MODELS: dict[LlmProvider, str] = {
    "groq": "openai/gpt-oss-120b",
    "openrouter": "nvidia/nemotron-3.5-super-vl:free",
}
BASE_URLS: dict[LlmProvider, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


@dataclass(frozen=True)
class ExtractionResult:
    extraction: ModelExtraction
    usage: LlmUsage | None  # None for the rule-based parser


class ExtractionError(Exception):
    """Extraction did not produce a result.

    `usage` is set when the provider answered (and billed) before the failure, so the
    caller can still record the cost. Messages never contain inquiry content.
    """

    def __init__(self, message: str, *, usage: LlmUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class ExtractionNotConfigured(ExtractionError):
    """An LLM provider is selected but no API key is set."""


class ExtractionRateLimited(ExtractionError):
    """The provider answered 429."""


class ExtractionFailed(ExtractionError):
    """Timeout, HTTP error, or a response that is not valid JSON for the schema."""


class InquiryExtractor(Protocol):
    name: str  # fake, groq, openrouter
    step_kind: StepKind

    def extract(self, subject: str, body: str, reference_date: dt.date) -> ExtractionResult: ...


class UnconfiguredExtractor:
    """Stands in for an LLM provider without an API key; every call fails clearly."""

    step_kind: StepKind = "llm"

    def __init__(self, name: str) -> None:
        self.name = name

    def extract(self, subject: str, body: str, reference_date: dt.date) -> ExtractionResult:
        raise ExtractionNotConfigured(f"LLM provider {self.name} has no API key")


def get_extractor(settings: Annotated[Settings, Depends(get_settings)]) -> InquiryExtractor:
    """Extractor selected by settings; also a FastAPI dependency overridable in tests."""
    # Imported here: both implementations import the types defined above.
    from app.parsing.fake import RuleBasedExtractor
    from app.parsing.openai_compatible import OpenAICompatibleExtractor

    provider = settings.llm_provider
    if provider == "fake":
        return RuleBasedExtractor()
    if settings.llm_api_key is None:
        return UnconfiguredExtractor(provider)
    return OpenAICompatibleExtractor(
        name=provider,
        base_url=BASE_URLS[provider],
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model or DEFAULT_MODELS[provider],
        timeout_seconds=settings.llm_timeout_seconds,
    )
