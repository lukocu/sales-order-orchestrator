"""The labelled evaluation set: test inquiries with golden fields and the expected decision.

Labels are derived by hand from the rules and the seeded company data, never by running the
system; each case says why in `rationale`. Loading validates every case, so a wrong label or
field fails at load time, not in the middle of a run. `ParsedFields` is the same model the
analysis stores, so a change of that schema needs an update of `cases.json` as well.
"""

import re
from pathlib import Path
from typing import Self

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

    @field_validator("id")
    @classmethod
    def _kebab_case(cls, value: str) -> str:
        if not _KEBAB_CASE.fullmatch(value):
            raise ValueError("id must be kebab-case")
        return value


_CASES = TypeAdapter(list[EvalCase])


class DuplicateCaseId(ValueError):
    """Two cases of one set share an id."""


def load_cases(path: Path | None = None) -> list[EvalCase]:
    """The cases of `path` (by default the built-in `cases.json`), in file order.

    Raises `pydantic.ValidationError` for an invalid case and `DuplicateCaseId` when an id
    repeats.
    """
    cases = _CASES.validate_json((path or CASES_PATH).read_bytes())
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise DuplicateCaseId(f"Case id {case.id} is used more than once")
        seen.add(case.id)
    return cases
