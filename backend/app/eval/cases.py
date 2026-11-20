"""The labelled evaluation set: test inquiries with golden fields and the expected decision.

Labels are derived by hand from the rules and the seeded company data, never by running the
system; each case says why in `rationale`. Loading validates every case, so a wrong label or
field fails at load time, not in the middle of a run. `ParsedFields` is the same model the
analysis stores, so a change of that schema needs an update of `cases.json` as well.
"""

import re
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.checks.schema import Outcome
from app.parsing.schema import ParsedFields
from app.policy.schema import PolicyOutcome
from app.recommendation.schema import OptionKind

CASES_PATH = Path(__file__).with_name("cases.json")

_KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

CaseTag = Literal[
    "unusual_discount",
    "price_deadline_conflict",
    "unclear_requirements",
    "refused_substitute",
    "no_deadline",
    "adversarial",
    "rank_divergence",
]


class ExpectedDecision(BaseModel):
    """The decision a case should end in.

    The option kind and the policy outcome exist only for an exception: other outcomes never
    reach the orchestration.
    """

    model_config = ConfigDict(extra="forbid")

    checks_outcome: Outcome
    option_kind: OptionKind | None = None
    policy_outcome: PolicyOutcome | None = None

    @model_validator(mode="after")
    def _decision_only_for_exception(self) -> Self:
        exception = self.checks_outcome == "exception"
        for name, value in (
            ("option_kind", self.option_kind),
            ("policy_outcome", self.policy_outcome),
        ):
            if exception and value is None:
                raise ValueError(f"{name} is required for an exception")
            if not exception and value is not None:
                raise ValueError(f"{name} must be empty for checks outcome {self.checks_outcome}")
        return self


class EvalCase(BaseModel):
    """One test inquiry: the e-mail, its golden fields and the expected decision."""

    model_config = ConfigDict(extra="forbid")

    id: str
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_at: AwareDatetime
    fields: ParsedFields
    expected: ExpectedDecision
    rationale: str
    tags: list[CaseTag] = []
    # The decision the rule-based path reaches when it departs from `expected` (the label
    # from the PRD rules); requires the `rank_divergence` tag.
    rule_based: ExpectedDecision | None = None
    # Id of the clean twin of an adversarial case; set if and only if the tag is present.
    adversarial_of: str | None = None

    @field_validator("id")
    @classmethod
    def _kebab_case(cls, value: str) -> str:
        if not _KEBAB_CASE.fullmatch(value):
            raise ValueError("id must be kebab-case")
        return value

    @model_validator(mode="after")
    def _tags_agree_with_their_fields(self) -> Self:
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("tags must not repeat")
        if self.rule_based is not None and self.rule_based == self.expected:
            raise ValueError("rule_based must differ from expected")
        if (self.rule_based is not None) != ("rank_divergence" in self.tags):
            raise ValueError("rule_based and the rank_divergence tag go together")
        if (self.adversarial_of is not None) != ("adversarial" in self.tags):
            raise ValueError("adversarial_of and the adversarial tag go together")
        return self


_CASES = TypeAdapter(list[EvalCase])


class DuplicateCaseId(ValueError):
    """Two cases of one set share an id."""


class InvalidAdversarialTwin(ValueError):
    """An adversarial case does not match its clean twin."""


def load_cases(path: Path | None = None) -> list[EvalCase]:
    """The cases of `path` (by default the built-in `cases.json`), in file order.

    Raises `pydantic.ValidationError` for an invalid case, `DuplicateCaseId` when an id
    repeats and `InvalidAdversarialTwin` when an adversarial case does not match its twin.
    """
    cases = _CASES.validate_json((path or CASES_PATH).read_bytes())
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise DuplicateCaseId(f"Case id {case.id} is used more than once")
        seen.add(case.id)
    _check_adversarial_twins(cases)
    return cases


def _check_adversarial_twins(cases: list[EvalCase]) -> None:
    by_id = {case.id: case for case in cases}
    for case in cases:
        if case.adversarial_of is None:
            continue
        twin = by_id.get(case.adversarial_of)
        if twin is None:
            raise InvalidAdversarialTwin(
                f"Case {case.id} is adversarial of {case.adversarial_of}, which does not exist"
            )
        if twin.adversarial_of is not None:
            raise InvalidAdversarialTwin(f"Case {case.id} points at adversarial case {twin.id}")
        if case.fields != twin.fields or case.expected != twin.expected:
            raise InvalidAdversarialTwin(
                f"Case {case.id} must have the same fields and expected decision as {twin.id}"
            )
        if case.body == twin.body:
            raise InvalidAdversarialTwin(
                f"Case {case.id} must have a body different from {twin.id}"
            )
