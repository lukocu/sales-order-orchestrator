"""Shapes of the parsed inquiry fields.

`ParsedFields` is the validated result shared by storage and the API. `ModelExtraction` is
what the model (or the rule-based parser) returns: loose values without range checks, so a
bad value becomes an uncertain field in `app.parsing.analyze` instead of a failed call.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

FieldName = Literal[
    "customer", "product_code", "quantity", "deadline", "substitute_allowed", "price"
]
PriceKind = Literal["none", "best_price", "discount_percent", "target_price"]

MAX_TEXT_LENGTH = 200
# Kinds whose price_value is a number; the other kinds carry no value.
VALUED_PRICE_KINDS: frozenset[PriceKind] = frozenset({"discount_percent", "target_price"})


class ParsedFields(BaseModel):
    """Current values of an analysis (from the model, or corrected by a person)."""

    model_config = ConfigDict(extra="forbid")

    customer: str | None = Field(max_length=MAX_TEXT_LENGTH)
    product_code: str | None = Field(max_length=MAX_TEXT_LENGTH)
    quantity: int | None = Field(ge=1)
    deadline: date | None
    deadline_text: str | None = Field(max_length=MAX_TEXT_LENGTH)  # phrase as written
    substitute_allowed: bool | None
    price_kind: PriceKind
    price_value: Decimal | None  # percent for discount_percent, amount for target_price
    price_text: str | None = Field(max_length=MAX_TEXT_LENGTH)  # phrase as written

    @model_validator(mode="after")
    def _price_value_matches_kind(self) -> Self:
        value = self.price_value
        if self.price_kind not in VALUED_PRICE_KINDS:
            if value is not None:
                raise ValueError(f"price_value must be empty for price_kind {self.price_kind}")
        elif value is None:
            raise ValueError(f"price_value is required for price_kind {self.price_kind}")
        elif not value.is_finite():
            raise ValueError("price_value must be a finite number")
        elif self.price_kind == "discount_percent" and not 0 < value <= 100:
            raise ValueError("discount percent must be above 0 and at most 100")
        elif self.price_kind == "target_price" and value <= 0:
            raise ValueError("target price must be above 0")
        return self


class UncertainItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: FieldName
    reason: str


class ModelExtraction(BaseModel):
    """Structured output of the extraction step.

    Every field is required and has no default, so the JSON schema meets the strict
    structured-output rules (all properties required, no additional properties).
    """

    model_config = ConfigDict(extra="forbid")

    customer: str | None
    product_code: str | None
    quantity: int | None
    deadline_text: str | None
    deadline_date: str | None  # ISO date as computed by the model; resolved again in code
    substitute_allowed: bool | None
    price_kind: PriceKind
    price_value: float | None
    price_text: str | None
    uncertain: list[UncertainItem]


def model_extraction_json_schema() -> dict[str, Any]:
    """JSON schema of `ModelExtraction` for `response_format` (strict mode).

    References are inlined, titles dropped and `anyOf: [X, null]` turned into a type list
    (`["string", "null"]`), the form the strict mode documents for optional fields.
    """
    schema = ModelExtraction.model_json_schema()
    definitions = schema.pop("$defs", {})
    simplified: dict[str, Any] = _simplify(schema, definitions)
    return simplified


def _simplify(node: Any, definitions: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_simplify(item, definitions) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str):
        return _simplify(definitions[ref.removeprefix("#/$defs/")], definitions)
    result = {
        key: _simplify(value, definitions)
        for key, value in node.items()
        if key not in ("title", "default")
    }
    options = result.get("anyOf")
    if isinstance(options, list) and _is_nullable_scalar(options):
        (scalar,) = (option for option in options if option != {"type": "null"})
        del result["anyOf"]
        result.update(scalar)
        result["type"] = [scalar["type"], "null"]
    return result


def _is_nullable_scalar(options: list[Any]) -> bool:
    if len(options) != 2 or {"type": "null"} not in options:
        return False
    other = next(option for option in options if option != {"type": "null"})
    return (
        isinstance(other, dict)
        and set(other) == {"type"}
        and isinstance(other["type"], str)
        and other["type"] != "object"
    )
