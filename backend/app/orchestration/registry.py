"""Static registry of capabilities and agents (in the spirit of A2A "Agent Cards").

Every capability has a description and its prerequisites; every agent declares the
capabilities it serves. Dependency edges come only from here, never from the planner, so the
planner cannot drop a prerequisite. The planner prompt and its closed list of capabilities are
built from `CAPABILITIES`.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Engine

from app.orchestration.agents import (
    AgentInput,
    run_catalog_agent,
    run_history_agent,
    run_supplier_agent,
    run_warehouse_agent,
)
from app.orchestration.schema import AgentResult, Capability

MismatchCode = Literal["no_agent", "ambiguous_agent"]


@dataclass(frozen=True)
class CapabilitySpec:
    name: Capability
    description: str
    depends_on: tuple[Capability, ...] = ()


@dataclass(frozen=True)
class AgentSpec:
    name: str
    capabilities: tuple[Capability, ...]
    run: Callable[[Engine, AgentInput], AgentResult]


# Order matters: tasks inside a stage are listed in this order.
CAPABILITIES: dict[Capability, CapabilitySpec] = {
    spec.name: spec
    for spec in (
        CapabilitySpec(
            name="substitute-compatibility",
            description="Find catalogue products that can replace the requested one, "
            "with their compatibility (full or partial).",
        ),
        CapabilitySpec(
            name="substitute-availability",
            description="Check the stock of each compatible substitute and whether it covers "
            "the shortage.",
            depends_on=("substitute-compatibility",),
        ),
        CapabilitySpec(
            name="supplier-availability",
            description="Check supplier offers for the requested product: quantity, delivery "
            "date and whether it meets the deadline.",
        ),
        CapabilitySpec(
            name="customer-history",
            description="Check the customer's past orders and whether they accepted "
            "substitutes before.",
        ),
    )
}

AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        name="catalog-agent", capabilities=("substitute-compatibility",), run=run_catalog_agent
    ),
    AgentSpec(
        name="warehouse-agent", capabilities=("substitute-availability",), run=run_warehouse_agent
    ),
    AgentSpec(
        name="supplier-agent", capabilities=("supplier-availability",), run=run_supplier_agent
    ),
    AgentSpec(name="history-agent", capabilities=("customer-history",), run=run_history_agent),
)


class CapabilityMismatch(Exception):
    """A capability has no agent, or more than one, in the registry."""

    def __init__(self, code: MismatchCode, capability: Capability) -> None:
        detail = "no agent" if code == "no_agent" else "more than one agent"
        super().__init__(f"Capability {capability} has {detail}")
        self.code: MismatchCode = code
        self.capability: Capability = capability


def match_agents(
    capabilities: Iterable[Capability], agents: Sequence[AgentSpec] = AGENTS
) -> dict[Capability, AgentSpec]:
    """Exactly one agent for every capability, in the given order."""
    matched: dict[Capability, AgentSpec] = {}
    for capability in capabilities:
        candidates = [a for a in agents if capability in a.capabilities]
        if not candidates:
            raise CapabilityMismatch("no_agent", capability)
        if len(candidates) > 1:
            raise CapabilityMismatch("ambiguous_agent", capability)
        matched[capability] = candidates[0]
    return matched
