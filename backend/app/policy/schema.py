"""Shape of a policy verdict, stored as JSONB in `inquiry_policy_verdicts.result`.

Written with `PolicyResult.model_dump(mode="json")` (Decimal values become strings) and read
with `model_validate`. Any later change to these models needs a data migration of the stored
rows, or a new optional field with a default (context/foundation/lessons.md).
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

RuleCode = Literal["margin", "discount", "order_value", "credit"]
RuleVerdict = Literal["pass", "fail", "not_evaluated"]
PolicyOutcome = Literal["no_approval_needed", "requires_supervisor"]
# Codes of the configurable thresholds (rows of `policy_rules`); credit uses the customer limit.
ThresholdCode = Literal["margin_min_percent", "discount_max_percent", "order_value_max"]
Unit = Literal["percent", "PLN"]


class RuleResult(BaseModel):
    """One rule: the actual value next to its threshold, the verdict and a short reason.

    The reason is a fixed English sentence; it never carries data from the inquiry's e-mail.
    """

    model_config = ConfigDict(extra="forbid")

    code: RuleCode
    verdict: RuleVerdict
    actual: Decimal | None
    threshold: Decimal | None
    unit: Unit
    reason: str


class PolicyResult(BaseModel):
    """Every rule of one evaluation (always margin, discount, order_value, credit) and the
    overall outcome."""

    model_config = ConfigDict(extra="forbid")

    option_id: str
    rules: list[RuleResult]
    outcome: PolicyOutcome
    thresholds_are_examples: bool
