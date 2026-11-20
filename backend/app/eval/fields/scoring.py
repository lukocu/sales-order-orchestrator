"""Classify each parsed field against its label and count the outcomes.

`hit`: the value is right (and flagged when the label says it must be). `flagged_miss`: wrong
or missing but marked uncertain, acceptable under PRD FR-002. `silent_wrong`: wrong, or lacking
a required flag, and not marked: the failure the eval exists to find.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from app.checks.rules import _contains_words, normalize_name
from app.eval.fields.cases import FieldCase, FieldTag
from app.parsing.schema import FieldName, ParsedFields

FieldOutcome = Literal["hit", "flagged_miss", "silent_wrong"]

FIELD_NAMES: tuple[FieldName, ...] = get_args(FieldName)

# The one field each tag is about, so an error there is not diluted by the other five fields.
TAG_FIELD: dict[FieldTag, FieldName] = {
    "deadline_supported": "deadline",
    "deadline_unsupported": "deadline",
    "deadline_absent": "deadline",
    "weekend_reference": "deadline",
    "year_rollover": "deadline",
    "substitute_stated": "substitute_allowed",
    "substitute_absent": "substitute_allowed",
    "price_target": "price",
    "price_discount": "price",
    "price_best": "price",
    "price_absent": "price",
    "customer_signature": "customer",
    "customer_missing": "customer",
    "quantity_variant": "quantity",
}


def _customer_matches(label: str | None, result: str | None) -> bool:
    if label is None or result is None:
        return label is None and result is None
    return _contains_words(normalize_name(result), normalize_name(label))


def _product_matches(label: str | None, result: str | None) -> bool:
    if label is None or result is None:
        return label is None and result is None
    return label.strip().lower() == result.strip().lower()


def score_case(
    case: FieldCase, parsed: ParsedFields, uncertain: dict[FieldName, str]
) -> dict[FieldName, FieldOutcome]:
    """The outcome of each of the six fields of one parse."""
    expected = case.expected
    correct: dict[FieldName, bool] = {
        "customer": _customer_matches(expected.customer.value, parsed.customer),
        "product_code": _product_matches(expected.product_code.value, parsed.product_code),
        "quantity": parsed.quantity == expected.quantity.value,
        "deadline": parsed.deadline == expected.deadline.value,
        "substitute_allowed": parsed.substitute_allowed == expected.substitute_allowed.value,
        "price": (
            parsed.price_kind == expected.price.kind and parsed.price_value == expected.price.value
        ),
    }
    needs_flag: dict[FieldName, bool] = {
        "customer": expected.customer.flagged,
        "product_code": expected.product_code.flagged,
        "quantity": expected.quantity.flagged,
        "deadline": expected.deadline.flagged,
        "substitute_allowed": expected.substitute_allowed.flagged,
        "price": expected.price.flagged,
    }
    outcomes: dict[FieldName, FieldOutcome] = {}
    for name in FIELD_NAMES:
        flagged = name in uncertain
        if correct[name] and (flagged or not needs_flag[name]):
            outcomes[name] = "hit"
        elif flagged and not correct[name]:
            outcomes[name] = "flagged_miss"
        else:
            outcomes[name] = "silent_wrong"
    return outcomes


@dataclass
class Tally:
    hits: int = 0
    flagged_misses: int = 0
    silent_wrongs: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.flagged_misses + self.silent_wrongs

    def add(self, outcome: FieldOutcome) -> None:
        if outcome == "hit":
            self.hits += 1
        elif outcome == "flagged_miss":
            self.flagged_misses += 1
        else:
            self.silent_wrongs += 1


@dataclass
class FieldSummary:
    per_field: dict[FieldName, Tally]
    per_tag: dict[FieldTag, Tally]


# One case with the outcomes of each of its repeats (failed calls are left out by the caller).
CaseRepeats = tuple[FieldCase, Sequence[dict[FieldName, FieldOutcome]]]


def summarize(results: Sequence[CaseRepeats]) -> FieldSummary:
    """Counts per field and per tag over (case, repeat, field) units.

    A tag counts only the field it is about (`TAG_FIELD`).
    """
    per_field = {name: Tally() for name in FIELD_NAMES}
    per_tag: dict[FieldTag, Tally] = {}
    for case, repeats in results:
        for outcomes in repeats:
            for name, outcome in outcomes.items():
                per_field[name].add(outcome)
            for tag in case.tags:
                per_tag.setdefault(tag, Tally()).add(outcomes[TAG_FIELD[tag]])
    return FieldSummary(per_field=per_field, per_tag=per_tag)
