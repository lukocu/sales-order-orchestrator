"""Planner interface, the rule-based planner, plan validation and stages.

The model proposes, the code validates: a planner only picks capabilities from the closed
list; `validate_plan` enforces the rules (consent, prerequisites) and `stages` derives the
execution order from the registry's dependency edges.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from fastapi import Depends

from app.llm.client import BASE_URLS, DEFAULT_MODELS
from app.orchestration.registry import CAPABILITIES
from app.orchestration.schema import (
    Capability,
    PlanFacts,
    PlannedTask,
    PlannerChoice,
    SubstituteConsent,
)
from app.settings import Settings, get_settings
from app.tracing.models import StepKind
from app.tracing.pricing import LlmUsage

RejectionCode = Literal[
    "empty_plan",
    "too_many_tasks",
    "duplicate_capability",
    "substitute_refused",
    "missing_prerequisite",
]

SUBSTITUTE_CAPABILITIES: frozenset[Capability] = frozenset(
    {"substitute-compatibility", "substitute-availability"}
)


def substitute_consent(substitute_allowed: bool | None) -> SubstituteConsent:
    if substitute_allowed is None:
        return "unconfirmed"
    return "confirmed" if substitute_allowed else "refused"


@dataclass(frozen=True)
class PlanningResult:
    choice: PlannerChoice
    usage: LlmUsage | None  # None for the rule-based planner


class PlannerError(Exception):
    """The planner did not produce a choice.

    `usage` is set when the provider answered (and billed) before the failure, so the caller
    can still record the cost. `transient` errors (rate limit, timeout, HTTP 5xx, network) may
    be retried. Messages never contain inquiry content.
    """

    transient: bool = False

    def __init__(self, message: str, *, usage: LlmUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class PlannerNotConfigured(PlannerError):
    """An LLM provider is selected but no API key is set."""


class PlannerRateLimited(PlannerError):
    """The provider answered 429."""

    transient = True


class PlannerFailed(PlannerError):
    """Timeout, network or HTTP error, or a response that does not match the schema."""

    def __init__(self, message: str, *, transient: bool, usage: LlmUsage | None = None) -> None:
        super().__init__(message, usage=usage)
        self.transient = transient


class Planner(Protocol):
    name: str  # fake, groq, openrouter
    step_kind: StepKind

    def plan(self, facts: PlanFacts) -> PlanningResult: ...


class RuleBasedPlanner:
    """Every capability, without the substitute ones when the customer refused substitutes."""

    name = "fake"
    step_kind: StepKind = "deterministic"

    def plan(self, facts: PlanFacts) -> PlanningResult:
        shortage, code = facts.shortage, facts.product_code
        reasons: dict[Capability, str] = {
            "substitute-compatibility": (
                f"{code} is short by {shortage} pcs; look for compatible substitutes."
            ),
            "substitute-availability": (
                f"Check whether substitute stock covers the shortage of {shortage} pcs."
            ),
            "supplier-availability": (
                f"Check whether a supplier can deliver {shortage} pcs of {code}"
                + (" before the deadline." if facts.has_deadline else ".")
            ),
            "customer-history": "Check whether the customer accepted substitutes before.",
        }
        refused = facts.substitute_consent == "refused"
        tasks = [
            PlannedTask(capability=capability, reason=reason)
            for capability, reason in reasons.items()
            if not (refused and capability in SUBSTITUTE_CAPABILITIES)
        ]
        if refused:
            summary = (
                f"Shortage of {shortage} pcs of {code}; the customer refused substitutes, "
                "so only supplier delivery and order history are checked."
            )
        else:
            summary = (
                f"Shortage of {shortage} pcs of {code}; substitute consent is "
                f"{facts.substitute_consent}, so substitutes, supplier delivery and order "
                "history are checked."
            )
        return PlanningResult(choice=PlannerChoice(tasks=tasks, summary=summary), usage=None)


class UnconfiguredPlanner:
    """Stands in for an LLM provider without an API key; every call fails clearly."""

    step_kind: StepKind = "llm"

    def __init__(self, name: str) -> None:
        self.name = name

    def plan(self, facts: PlanFacts) -> PlanningResult:
        raise PlannerNotConfigured(f"LLM provider {self.name} has no API key")


def get_planner(settings: Annotated[Settings, Depends(get_settings)]) -> Planner:
    """Planner selected by settings (like `get_extractor`); a FastAPI dependency overridable
    in tests."""
    # Imported here: the LLM planner imports the types defined above.
    from app.orchestration.llm_planner import OpenAICompatiblePlanner

    provider = settings.llm_provider
    if provider == "fake":
        return RuleBasedPlanner()
    if settings.llm_api_key is None:
        return UnconfiguredPlanner(provider)
    return OpenAICompatiblePlanner(
        name=provider,
        base_url=BASE_URLS[provider],
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model or DEFAULT_MODELS[provider],
        timeout_seconds=settings.llm_timeout_seconds,
    )


class PlanRejected(Exception):
    """The planner's choice breaks a plan rule; `code` names the first rule broken."""

    def __init__(self, code: RejectionCode, message: str) -> None:
        super().__init__(message)
        self.code: RejectionCode = code


def validate_plan(choice: PlannerChoice, consent: SubstituteConsent) -> list[Capability]:
    """The planned capabilities in the planner's order, or `PlanRejected`.

    Rules are checked in a fixed order, so the reported code is deterministic.
    """
    capabilities = [task.capability for task in choice.tasks]
    if not capabilities:
        raise PlanRejected("empty_plan", "The plan has no tasks")
    if len(capabilities) > len(CAPABILITIES):
        raise PlanRejected(
            "too_many_tasks",
            f"The plan has {len(capabilities)} tasks, at most {len(CAPABILITIES)} are allowed",
        )
    seen: set[Capability] = set()
    for capability in capabilities:
        if capability in seen:
            raise PlanRejected("duplicate_capability", f"Capability {capability} is planned twice")
        seen.add(capability)
    if consent == "refused":
        for capability in capabilities:
            if capability in SUBSTITUTE_CAPABILITIES:
                raise PlanRejected(
                    "substitute_refused",
                    f"Capability {capability} is planned but the customer refused substitutes",
                )
    for capability in capabilities:
        for prerequisite in CAPABILITIES[capability].depends_on:
            if prerequisite not in seen:
                raise PlanRejected(
                    "missing_prerequisite",
                    f"Capability {capability} needs {prerequisite}, which is not planned",
                )
    return capabilities


def stages(capabilities: Sequence[Capability]) -> list[list[Capability]]:
    """Topological levels: a capability runs one stage after its latest planned prerequisite.

    Prerequisites that are not planned are ignored here (validation rejects such plans).
    Inside a stage, capabilities keep the order of `CAPABILITIES`.
    """
    planned = set(capabilities)
    levels: dict[Capability, int] = {}

    def level(capability: Capability) -> int:
        if capability not in levels:
            prerequisites = [p for p in CAPABILITIES[capability].depends_on if p in planned]
            levels[capability] = 1 + max((level(p) for p in prerequisites), default=-1)
        return levels[capability]

    result: list[list[Capability]] = []
    for capability in CAPABILITIES:
        if capability in planned:
            index = level(capability)
            while len(result) <= index:
                result.append([])
            result[index].append(capability)
    return [stage for stage in result if stage]
