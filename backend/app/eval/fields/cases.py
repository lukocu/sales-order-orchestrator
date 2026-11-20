"""The hand-labelled set of the parser field eval: one phrasing per case, labels per field.

Labels are derived by hand from the rules and a calendar, never by running the parser; each
case says why in `rationale`. Loading checks only invariants that do not depend on the code
under test (calendar weekday, not-before-reference-day, value ranges). It never calls the
deadline resolver, because a label computed by the code being measured would prove nothing.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.parsing.schema import VALUED_PRICE_KINDS, PriceKind

FIELD_CASES_PATH = Path(__file__).with_name("cases.json")

_KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_WARSAW = ZoneInfo("Europe/Warsaw")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

FieldTag = Literal[
    "deadline_supported",
    "deadline_unsupported",
    "deadline_absent",
    "weekend_reference",
    "year_rollover",
    "substitute_stated",
    "substitute_absent",
    "price_target",
    "price_discount",
    "price_best",
    "price_absent",
    "customer_signature",
    "customer_missing",
    "quantity_variant",
]


def reference_day(received_at: datetime) -> date:
    """The day the inquiry arrived, as seen in Poland (`reference_date_of` without the DB)."""
    return received_at.astimezone(_WARSAW).date()


class _Expectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The correct outcome is a value (or none) that the parser must also mark uncertain.
    flagged: bool = False


class _NullableExpectation(_Expectation):
    """A field the parser always flags when it is empty, so a null label must say so."""

    @model_validator(mode="after")
    def _null_is_flagged(self) -> Self:
        if getattr(self, "value", None) is None and not self.flagged:
            raise ValueError("a null value must be flagged: the parser always marks it")
        return self


class ExpectedText(_NullableExpectation):
    value: str | None

    @field_validator("value")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("a text label must not be blank (use null and flagged instead)")
        return value


class ExpectedQuantity(_NullableExpectation):
    value: int | None = Field(ge=1)


class ExpectedSubstitute(_NullableExpectation):
    value: bool | None


class ExpectedDeadline(_Expectation):
    # An absent deadline is legitimately unflagged, so null needs no flag here.
    value: date | None
    weekday: Weekday | None = None

    @model_validator(mode="after")
    def _weekday_matches_value(self) -> Self:
        if self.weekday is not None:
            if self.value is None:
                raise ValueError("weekday needs a deadline value")
            if _WEEKDAYS[self.value.weekday()] != self.weekday:
                raise ValueError(f"{self.value.isoformat()} is not a {self.weekday}")
        return self


class ExpectedPrice(_Expectation):
    kind: PriceKind
    value: Decimal | None = None

    @model_validator(mode="after")
    def _value_matches_kind(self) -> Self:
        value = self.value
        if self.kind not in VALUED_PRICE_KINDS:
            if value is not None:
                raise ValueError(f"value must be empty for kind {self.kind}")
        elif value is None:
            raise ValueError(f"value is required for kind {self.kind}")
        elif not value.is_finite():
            raise ValueError("value must be a finite number")
        elif self.kind == "discount_percent" and not 0 < value <= 100:
            raise ValueError("discount percent must be above 0 and at most 100")
        elif self.kind == "target_price" and value <= 0:
            raise ValueError("target price must be above 0")
        return self


class ExpectedFields(BaseModel):
    """The correct reading of each user-visible field."""

    model_config = ConfigDict(extra="forbid")

    customer: ExpectedText
    product_code: ExpectedText
    quantity: ExpectedQuantity
    deadline: ExpectedDeadline
    substitute_allowed: ExpectedSubstitute
    price: ExpectedPrice


class FieldCase(BaseModel):
    """One phrasing: the e-mail text, its reception time and the expected fields."""

    model_config = ConfigDict(extra="forbid")

    id: str
    subject: str
    body: str
    received_at: AwareDatetime
    expected: ExpectedFields
    rationale: str
    tags: list[FieldTag] = []

    @field_validator("id")
    @classmethod
    def _kebab_case(cls, value: str) -> str:
        if not _KEBAB_CASE.fullmatch(value):
            raise ValueError("id must be kebab-case")
        return value

    @field_validator("rationale")
    @classmethod
    def _rationale_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rationale must not be empty")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("tags must not repeat")
        deadline = self.expected.deadline.value
        reference = reference_day(self.received_at)
        if deadline is not None and deadline < reference:
            raise ValueError(
                f"deadline {deadline.isoformat()} is before the reference day "
                f"{reference.isoformat()}"
            )
        return self


_CASES = TypeAdapter(list[FieldCase])


class DuplicateFieldCaseId(ValueError):
    """Two cases of one set share an id."""


def load_cases(path: Path | None = None) -> list[FieldCase]:
    """The cases of `path` (by default the built-in `cases.json`), in file order.

    Raises `pydantic.ValidationError` for an invalid case and `DuplicateFieldCaseId` when an
    id repeats.
    """
    cases = _CASES.validate_json((path or FIELD_CASES_PATH).read_bytes())
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise DuplicateFieldCaseId(f"Case id {case.id} is used more than once")
        seen.add(case.id)
    return cases
