"""Drafter interface, the template drafter and text validation.

The code assembles every number of the reply (`app.draft.offer.render_body`); a drafter only
writes the intro and the closing paragraph around them, from `DraftFacts`, which carry no
numbers. `validate_text` rejects a paragraph with a digit, a number word, a percent sign, a
link or an e-mail address, or over the length limit, so no number, term or address in the
e-mail can come from a model (the facts carry customer text, so a prompt injection is assumed).
"""

import re
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from fastapi import Depends
from pydantic import BaseModel, ConfigDict

from app.llm.client import BASE_URLS, DEFAULT_MODELS
from app.recommendation.schema import OptionKind
from app.settings import Settings, get_settings
from app.tracing.models import StepKind
from app.tracing.pricing import LlmUsage

MAX_PARAGRAPH_LENGTH = 600

RejectionCode = Literal[
    "text_empty", "text_has_digit", "text_has_number_word", "text_has_link", "text_too_long"
]

# Numbers spelled out in Polish (inflected forms) and percent words. "jeden"/"jedna" are left
# out: their stem also starts common words ("jednak", "jednocześnie").
NUMBER_WORDS = re.compile(
    r"\b("
    r"zer[oa]|dw(a|ie|óch|oma|u)|trz(y|ech|ema|eci\w*)|czter\w*|pię[ćc]\w*|sze[śs][ćc]\w*"
    r"|siedem|siedm\w*|osiem|ośm\w*|dziewię[ćc]\w*|dziesię[ćc]\w*|\w+naści\w*|\w+dzieści\w*"
    r"|\w+set|sto|stu|tysi[ąę]c\w*|milion\w*|procent\w*|pół|połow\w*"
    r")\b",
    re.IGNORECASE,
)
LINK = re.compile(r"://|\bwww\.|@", re.IGNORECASE)

# Used when the drafter fails or its text is rejected on every attempt.
FALLBACK_INTRO = (
    "Dziękujemy za przesłane zapytanie. Poniżej przedstawiamy naszą propozycję realizacji "
    "zamówienia."
)
FALLBACK_CLOSING = (
    "Prosimy o potwierdzenie propozycji lub informację o potrzebnych zmianach. W razie pytań "
    "pozostajemy do dyspozycji."
)


class DraftFacts(BaseModel):
    """What the drafter sees about the inquiry and the offer; no numbers of the offer."""

    model_config = ConfigDict(extra="forbid")

    customer: str | None  # the customer's company, None when not matched
    sender_name: str
    subject: str
    option_kind: OptionKind
    meets_deadline: bool | None  # None when the inquiry has no deadline
    has_substitute: bool
    has_supplier: bool
    signals: list[str]  # Polish labels of the signals the recommendation cites
    justification: str  # the recommendation's justification


@dataclass(frozen=True)
class DrafterOutput:
    intro: str
    closing: str
    usage: LlmUsage | None  # None for the template drafter


class DrafterError(Exception):
    """The drafter did not produce the paragraphs.

    `usage` is set when the provider answered (and billed) before the failure, so the caller
    can still record the cost. `transient` errors (rate limit, timeout, HTTP 5xx, network) may
    be retried. Messages never contain inquiry content.
    """

    transient: bool = False

    def __init__(self, message: str, *, usage: LlmUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class DrafterNotConfigured(DrafterError):
    """An LLM provider is selected but no API key is set."""


class DrafterRateLimited(DrafterError):
    """The provider answered 429."""

    transient = True


class DrafterFailed(DrafterError):
    """Timeout, network or HTTP error, or a response that does not match the schema."""

    def __init__(self, message: str, *, transient: bool, usage: LlmUsage | None = None) -> None:
        super().__init__(message, usage=usage)
        self.transient = transient


class Drafter(Protocol):
    name: str  # fake, groq, openrouter
    step_kind: StepKind

    def write(self, facts: DraftFacts) -> DrafterOutput: ...


_KIND_INTRO: dict[OptionKind, str] = {
    "partial_delivery": "w formie dostawy częściowej z naszego magazynu",
    "substitute": "z udziałem produktu zamiennego o zgodnych parametrach",
    "other_source": "z dostawą od naszego sprawdzonego dostawcy",
    "combined": "łączącą produkt zamienny i dostawę od naszego dostawcy",
}


class FakeDrafter:
    """Writes the paragraphs from a fixed Polish template; never a digit."""

    name = "fake"
    step_kind: StepKind = "deterministic"

    def write(self, facts: DraftFacts) -> DrafterOutput:
        proposal = _KIND_INTRO[facts.option_kind]
        intro = (
            "Dziękujemy za przesłane zapytanie. Nie mamy obecnie na stanie pełnej zamówionej "
            f"ilości, dlatego przygotowaliśmy propozycję realizacji {proposal}."
        )
        if facts.meets_deadline is True:
            closing = (
                "Proponowany termin realizacji mieści się w oczekiwanym przez Państwa terminie."
            )
        elif facts.meets_deadline is False:
            closing = (
                "Proponowany termin realizacji jest niestety późniejszy niż oczekiwany. Prosimy "
                "o informację, czy jest on dla Państwa akceptowalny."
            )
        else:
            closing = "Termin realizacji podajemy powyżej."
        closing += " Prosimy o potwierdzenie propozycji. W razie pytań pozostajemy do dyspozycji."
        return DrafterOutput(intro=intro, closing=closing, usage=None)


class UnconfiguredDrafter:
    """Stands in for an LLM provider without an API key; every call fails clearly."""

    step_kind: StepKind = "llm"

    def __init__(self, name: str) -> None:
        self.name = name

    def write(self, facts: DraftFacts) -> DrafterOutput:
        raise DrafterNotConfigured(f"LLM provider {self.name} has no API key")


def get_drafter(settings: Annotated[Settings, Depends(get_settings)]) -> Drafter:
    """Drafter selected by settings (like `get_recommender`); a FastAPI dependency
    overridable in tests."""
    # Imported here: the LLM drafter imports the types defined above.
    from app.draft.llm_drafter import OpenAICompatibleDrafter

    provider = settings.llm_provider
    if provider == "fake":
        return FakeDrafter()
    if settings.llm_api_key is None:
        return UnconfiguredDrafter(provider)
    return OpenAICompatibleDrafter(
        name=provider,
        base_url=BASE_URLS[provider],
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model or DEFAULT_MODELS[provider],
        timeout_seconds=settings.llm_timeout_seconds,
    )


class TextRejected(Exception):
    """A paragraph breaks a rule; `code` names the first rule broken."""

    def __init__(self, code: RejectionCode, message: str) -> None:
        super().__init__(message)
        self.code: RejectionCode = code


def validate_text(output: DrafterOutput) -> None:
    """`TextRejected` when a paragraph is empty, has a digit, a number word or `%`, a link or
    an e-mail address, or is too long; intro first."""
    for paragraph in (output.intro, output.closing):
        if not paragraph.strip():
            raise TextRejected("text_empty", "A paragraph is empty")
        if any(char.isdigit() for char in paragraph):
            raise TextRejected("text_has_digit", "A paragraph contains a digit")
        if "%" in paragraph or NUMBER_WORDS.search(paragraph):
            raise TextRejected("text_has_number_word", "A paragraph contains a number word")
        if LINK.search(paragraph):
            raise TextRejected("text_has_link", "A paragraph contains a link or an address")
        if len(paragraph) > MAX_PARAGRAPH_LENGTH:
            raise TextRejected("text_too_long", "A paragraph is too long")
