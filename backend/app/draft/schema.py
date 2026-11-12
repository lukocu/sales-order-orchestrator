"""Shape of a reply draft and of a decision snapshot, stored as JSONB in
`inquiry_drafts.result` and `inquiry_draft_decisions.snapshot`.

Written with `model_dump(mode="json")` (Decimal and date values become strings) and read with
`model_validate`. Any later change to these models needs a data migration of the stored rows,
or a new optional field with a default (context/foundation/lessons.md).

Every number of the offer is computed by code; the drafter only writes the intro and the
closing paragraph, without digits.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.policy.schema import PolicyOutcome, PolicyResult, RuleCode
from app.recommendation.schema import LineSource, OptionKind

DraftStatus = Literal["draft", "ready_to_send", "awaiting_supervisor", "rejected"]
DecisionAction = Literal["edit", "approve", "reject"]
TextSource = Literal["model", "fallback"]


class OfferLine(BaseModel):
    """One line of the offer: an option line with the list price of its product."""

    model_config = ConfigDict(extra="forbid")

    product_code: str
    product_name: str
    source: LineSource
    supplier: str | None = None  # only for `supplier` lines
    quantity: int
    available_on: date
    list_price: Decimal  # catalogue price of the line's product
    unit_price: Decimal  # PLN net, offered to the customer
    unit_cost: Decimal
    value: Decimal
    cost: Decimal


class DraftOffer(BaseModel):
    """The offer of the draft: the chosen option as computed, or its edit."""

    model_config = ConfigDict(extra="forbid")

    option_id: str
    kind: OptionKind
    lines: list[OfferLine]
    covered_quantity: int
    requested_quantity: int
    fulfilled_on: date
    meets_deadline: bool | None  # None when the inquiry has no deadline
    value: Decimal
    cost: Decimal
    margin_percent: Decimal
    edited: bool


class DraftText(BaseModel):
    """The two paragraphs around the offer; never carries digits."""

    model_config = ConfigDict(extra="forbid")

    intro: str
    closing: str
    source: TextSource
    error: str | None = None  # error code when the fallback text replaced the model's


class DraftResult(BaseModel):
    """Everything of the current draft. The status lives in its own column."""

    model_config = ConfigDict(extra="forbid")

    drafter: str  # drafter name, e.g. fake, groq
    offer: DraftOffer
    text: DraftText
    # The policy verdict of an edited offer; None for the offer as recommended, whose verdict
    # is the policy stage's own.
    policy: PolicyResult | None = None


class DecisionSnapshot(BaseModel):
    """What a decision was about: the offer and the policy verdict in force at that time."""

    model_config = ConfigDict(extra="forbid")

    offer: DraftOffer
    policy_outcome: PolicyOutcome | None
    failing_rules: list[RuleCode] = Field(default_factory=list)
