"""Shape of an orchestration result, stored as JSONB in `inquiry_orchestrations.result`.

Written with `OrchestrationResult.model_dump(mode="json")` and read with `model_validate`. Any
later change to these models needs a data migration of the stored rows, or a new optional
field with a default (context/foundation/lessons.md).

`PlanFacts` is what the planner sees: structured facts only, never the inquiry's e-mail text.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.checks.schema import ExceptionType

Capability = Literal[
    "substitute-compatibility",
    "substitute-availability",
    "supplier-availability",
    "customer-history",
]
# From `ParsedFields.substitute_allowed`: True / False / None.
SubstituteConsent = Literal["confirmed", "refused", "unconfirmed"]
OrchestrationStatus = Literal["completed", "partial", "failed"]
TaskStatus = Literal["completed", "failed", "skipped"]
Compatibility = Literal["full", "partial"]
HistorySignal = Literal["accepted_before", "declined_before", "mixed", "no_substitute_history"]
OrchestrationErrorKind = Literal["planner_failed", "plan_rejected", "capability_mismatch"]

MAX_REASON_LENGTH = 300
MAX_SUMMARY_LENGTH = 500


# --- Planner and plan -----------------------------------------------------------------


class PlannedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Capability
    reason: str = Field(max_length=MAX_REASON_LENGTH)


class PlannerChoice(BaseModel):
    """The planner's raw answer, before validation."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[PlannedTask]
    summary: str = Field(max_length=MAX_SUMMARY_LENGTH)


class PlanFacts(BaseModel):
    """What the planner sees about the inquiry; no e-mail content."""

    model_config = ConfigDict(extra="forbid")

    exception_type: ExceptionType
    product_code: str
    requested: int
    available: int
    shortage: int
    has_deadline: bool
    substitute_consent: SubstituteConsent
    customer_known: bool


# --- Agent results ----------------------------------------------------------------------


class SubstituteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    compatibility: Compatibility
    note: str


class SubstituteCompatibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Literal["substitute-compatibility"] = "substitute-compatibility"
    candidates: list[SubstituteCandidate]  # full compatibility first, then by code


class SubstituteStock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    stock: int
    covers_shortage: bool  # stock >= shortage


class SubstituteAvailabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Literal["substitute-availability"] = "substitute-availability"
    candidates: list[SubstituteStock]


class SupplierDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier: str
    quantity: int
    lead_time_days: int
    available_on: date  # reference_date + lead_time_days
    meets_deadline: bool | None  # None when the inquiry has no deadline
    covers_shortage: bool  # quantity >= shortage


class SupplierAvailabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Literal["supplier-availability"] = "supplier-availability"
    offers: list[SupplierDelivery]


class CustomerHistoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Literal["customer-history"] = "customer-history"
    orders_count: int
    substitutes_offered: int
    substitutes_accepted: int
    signal: HistorySignal


AgentResult = Annotated[
    SubstituteCompatibilityResult
    | SubstituteAvailabilityResult
    | SupplierAvailabilityResult
    | CustomerHistoryResult,
    Field(discriminator="capability"),
]


# --- Orchestration result -------------------------------------------------------------


class TaskOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Capability
    agent: str
    reason: str
    depends_on: list[Capability]
    stage: int  # 1-based
    status: TaskStatus
    steps: list[str]  # trace step names, one per attempt; empty when skipped
    error_type: str | None = None  # exception class name only
    result: AgentResult | None = None


class OrchestrationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: OrchestrationErrorKind
    code: str  # e.g. substitute_refused, missing_prerequisite, no_agent, rate_limited
    message: str  # English, never inquiry content


class OrchestrationResult(BaseModel):
    """Everything of one orchestration run. The status is stored in its own column."""

    model_config = ConfigDict(extra="forbid")

    consent: SubstituteConsent
    planner: str  # planner name, e.g. fake, groq
    planner_choice: PlannerChoice | None = None  # kept also when the plan was rejected
    planner_steps: list[str] = Field(default_factory=list)
    tasks: list[TaskOutcome] = Field(default_factory=list)
    error: OrchestrationError | None = None
