"""Recommender interface, the rule-based recommender and choice validation.

The code builds and scores the options; a recommender only picks one of them and writes the
justification. `validate_choice` checks that the pick and the cited signals belong to the
options, so numbers shown to the salesperson always come from the options themselves.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from fastapi import Depends

from app.llm.client import BASE_URLS, DEFAULT_MODELS
from app.recommendation.schema import (
    MAX_JUSTIFICATION_LENGTH,
    ConfidenceBand,
    RecommendationFacts,
    RecommendationOption,
    RecommenderChoice,
)
from app.settings import Settings, get_settings
from app.tracing.models import StepKind
from app.tracing.pricing import LlmUsage

RejectionCode = Literal["unknown_option", "foreign_signal", "empty_justification"]

BAND_RANK: dict[ConfidenceBand, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


@dataclass(frozen=True)
class RecommenderOutput:
    choice: RecommenderChoice
    usage: LlmUsage | None  # None for the rule-based recommender


class RecommenderError(Exception):
    """The recommender did not produce a choice.

    `usage` is set when the provider answered (and billed) before the failure, so the caller
    can still record the cost. `transient` errors (rate limit, timeout, HTTP 5xx, network) may
    be retried. Messages never contain inquiry content.
    """

    transient: bool = False

    def __init__(self, message: str, *, usage: LlmUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class RecommenderNotConfigured(RecommenderError):
    """An LLM provider is selected but no API key is set."""


class RecommenderRateLimited(RecommenderError):
    """The provider answered 429."""

    transient = True


class RecommenderFailed(RecommenderError):
    """Timeout, network or HTTP error, or a response that does not match the schema."""

    def __init__(self, message: str, *, transient: bool, usage: LlmUsage | None = None) -> None:
        super().__init__(message, usage=usage)
        self.transient = transient


class Recommender(Protocol):
    name: str  # rule-based, groq, openrouter
    step_kind: StepKind

    def choose(
        self, facts: RecommendationFacts, options: Sequence[RecommendationOption]
    ) -> RecommenderOutput: ...


def rank(options: Sequence[RecommendationOption]) -> list[RecommendationOption]:
    """Band (HIGH first), then covered quantity, earlier date, higher margin, id."""
    return sorted(
        options,
        key=lambda o: (
            BAND_RANK[o.band],
            -o.covered_quantity,
            o.fulfilled_on,
            -o.margin_percent,
            o.id,
        ),
    )


class FakeRecommender:
    """Picks the best-ranked option and justifies it from a template."""

    name = "rule-based"
    step_kind: StepKind = "deterministic"

    def choose(
        self, facts: RecommendationFacts, options: Sequence[RecommendationOption]
    ) -> RecommenderOutput:
        if not options:
            raise RecommenderFailed("There are no options to choose from", transient=False)
        best = rank(options)[0]
        cited = [s for s in best.signals if s.polarity != "info"]
        positives = [s.label for s in cited if s.polarity == "positive"]
        risks = [s.label for s in cited if s.polarity == "risk"]
        justification = (
            f"Wybrano opcję {best.id}: pokrycie {best.covered_quantity}/"
            f"{best.requested_quantity} szt., realizacja {best.fulfilled_on.isoformat()}, "
            f"marża {best.margin_percent}%, pewność {best.band}."
        )
        if positives:
            justification += f" Za: {'; '.join(positives)}."
        if risks:
            justification += f" Ryzyka: {'; '.join(risks)}."
        if len(justification) > MAX_JUSTIFICATION_LENGTH:
            justification = justification[: MAX_JUSTIFICATION_LENGTH - 1] + "…"
        choice = RecommenderChoice(
            option_id=best.id,
            justification=justification,
            cited_signals=[s.code for s in cited],
        )
        return RecommenderOutput(choice=choice, usage=None)


class UnconfiguredRecommender:
    """Stands in for an LLM provider without an API key; every call fails clearly."""

    step_kind: StepKind = "llm"

    def __init__(self, name: str) -> None:
        self.name = name

    def choose(
        self, facts: RecommendationFacts, options: Sequence[RecommendationOption]
    ) -> RecommenderOutput:
        raise RecommenderNotConfigured(f"LLM provider {self.name} has no API key")


def get_recommender(settings: Annotated[Settings, Depends(get_settings)]) -> Recommender:
    """Recommender selected by settings (like `get_planner`); a FastAPI dependency
    overridable in tests."""
    # Imported here: the LLM recommender imports the types defined above.
    from app.recommendation.llm_recommender import OpenAICompatibleRecommender

    provider = settings.llm_provider
    if provider == "fake":
        return FakeRecommender()
    if settings.llm_api_key is None:
        return UnconfiguredRecommender(provider)
    return OpenAICompatibleRecommender(
        name=provider,
        base_url=BASE_URLS[provider],
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model or DEFAULT_MODELS[provider],
        timeout_seconds=settings.llm_timeout_seconds,
    )


class ChoiceRejected(Exception):
    """The recommender's choice breaks a rule; `code` names the first rule broken."""

    def __init__(self, code: RejectionCode, message: str) -> None:
        super().__init__(message)
        self.code: RejectionCode = code


def validate_choice(choice: RecommenderChoice, options: Sequence[RecommendationOption]) -> None:
    """`ChoiceRejected` when the choice does not fit the options; rules in a fixed order."""
    chosen = next((o for o in options if o.id == choice.option_id), None)
    if chosen is None:
        raise ChoiceRejected("unknown_option", "The chosen option does not exist")
    codes = {s.code for s in chosen.signals}
    for cited in choice.cited_signals:
        if cited not in codes:
            raise ChoiceRejected(
                "foreign_signal", "A cited signal does not belong to the chosen option"
            )
    if not choice.justification.strip():
        raise ChoiceRejected("empty_justification", "The justification is empty")
