"""Shape of a recommendation result, stored as JSONB in `inquiry_recommendations.result`.

Written with `RecommendationResult.model_dump(mode="json")` (Decimal values become strings)
and read with `model_validate`. Any later change to these models needs a data migration of
the stored rows, or a new optional field with a default (context/foundation/lessons.md).

The code computes every number and band; the recommender only picks one of the options and
writes the justification. `RecommendationFacts` is what the recommender sees about the
inquiry: structured facts only, never the inquiry's e-mail text.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.orchestration.schema import HistorySignal, SubstituteConsent

# `combined` takes the shortage from a substitute and a supplier together.
OptionKind = Literal["partial_delivery", "substitute", "other_source", "combined"]
LineSource = Literal["stock", "substitute_stock", "supplier"]
SignalPolarity = Literal["positive", "risk", "info"]
ConfidenceBand = Literal["HIGH", "MEDIUM", "LOW"]
RecommendationErrorKind = Literal["recommender_failed", "choice_rejected"]

MAX_JUSTIFICATION_LENGTH = 1000


class OptionLine(BaseModel):
    """One source of an option: a product, a quantity, where it comes from and when."""

    model_config = ConfigDict(extra="forbid")

    product_code: str
    product_name: str
    source: LineSource
    supplier: str | None = None  # only for `supplier` lines
    quantity: int
    available_on: date
    unit_price: Decimal  # list price of the offered product less the customer's discount
    unit_cost: Decimal
    value: Decimal
    cost: Decimal


class Signal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str  # e.g. full_coverage, task_failed:customer-history
    polarity: SignalPolarity
    label: str  # Polish text for the UI


class RecommendationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str  # stable and readable, e.g. stock+ABC-110, stock+supplier:Hydro-Valve
    kind: OptionKind
    lines: list[OptionLine]
    covered_quantity: int
    requested_quantity: int
    fulfilled_on: date  # the latest date of the lines
    meets_deadline: bool | None  # None when the inquiry has no deadline
    value: Decimal
    cost: Decimal
    margin_percent: Decimal
    band: ConfidenceBand
    signals: list[Signal]


class RecommenderChoice(BaseModel):
    """The recommender's raw answer, before validation."""

    model_config = ConfigDict(extra="forbid")

    option_id: str
    justification: str = Field(max_length=MAX_JUSTIFICATION_LENGTH)
    cited_signals: list[str]  # signal codes of the chosen option


class RecommendationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: RecommendationErrorKind
    code: str  # e.g. unknown_option, foreign_signal, rate_limited
    message: str  # English, never inquiry content


class RecommendationResult(BaseModel):
    """Everything of one recommendation run. The status is stored in its own column."""

    model_config = ConfigDict(extra="forbid")

    recommender: str  # recommender name, e.g. rule-based, groq
    options: list[RecommendationOption] = Field(default_factory=list)
    choice: RecommenderChoice | None = None  # None when the choice was rejected
    choice_steps: list[str] = Field(default_factory=list)  # trace step names, one per attempt
    error: RecommendationError | None = None


class RecommendationFacts(BaseModel):
    """What the recommender sees about the inquiry; no e-mail content."""

    model_config = ConfigDict(extra="forbid")

    product_code: str
    product_name: str
    requested: int
    available: int
    shortage: int
    deadline: date | None
    reference_date: date
    substitute_consent: SubstituteConsent
    discount_percent: Decimal  # the customer's standard discount
    uncertain_inputs: list[str]  # uncertain analysis fields: customer, product_code, quantity
    # None without a completed customer-history task.
    customer_history: HistorySignal | None
