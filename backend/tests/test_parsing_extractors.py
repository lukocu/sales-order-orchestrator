import json
from datetime import date
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.parsing.extractor import (
    ExtractionFailed,
    ExtractionNotConfigured,
    ExtractionRateLimited,
    UnconfiguredExtractor,
    get_extractor,
)
from app.parsing.fake import RuleBasedExtractor
from app.parsing.openai_compatible import MAX_BODY_CHARS, OpenAICompatibleExtractor
from app.parsing.schema import ModelExtraction, model_extraction_json_schema
from app.settings import Settings
from app.tracing.pricing import LlmUsage, price_usage

GROQ_MODEL = "openai/gpt-oss-120b"
REFERENCE = date(2026, 11, 2)  # Monday

# The four seed inquiries (migrations/versions/0003_users_inquiries.py).
ACME = (
    "Zapytanie ofertowe: 80 szt. ABC-100",
    "Dzień dobry,\n\n"
    "prosimy o ofertę na 80 szt. ABC-100 z dostawą do piątku. "
    "Jeśli nie mają Państwo pełnej ilości, możemy przyjąć podobny model "
    "o zbliżonych parametrach.\n\n"
    "Prosimy o najlepszą cenę i informację o terminie dostawy.\n\n"
    "Pozdrawiam,\nMarek Nowak\nDział zakupów, ACME Sp. z o.o.",
    date(2026, 11, 2),
)
BIURO_MAX = (
    "Zamówienie ABC-200, 20 szt.",
    "Dzień dobry,\n\n"
    "chcielibyśmy zamówić 20 szt. ABC-200 z dostawą do końca miesiąca. "
    "Proszę o przesłanie oferty z cenami i warunkami płatności.\n\n"
    "Z poważaniem,\nKatarzyna Zielińska\nBiuro Max",
    date(2026, 11, 3),
)
DELTA = (
    "500 szt. ABC-100 — prośba o rabat",
    "Dzień dobry,\n\n"
    "jesteśmy zainteresowani zakupem 500 szt. ABC-100. "
    "Przy takiej ilości prosimy o rabat 25% od ceny katalogowej.\n\n"
    "Czekamy na ofertę z terminem realizacji.\n\n"
    "Pozdrawiam,\nTomasz Lewandowski\nHurtownia Delta",
    date(2026, 11, 4),
)
OMEGA = (
    "Pilne: 120 szt. XYZ-300",
    "Dzień dobry,\n\n"
    "potrzebujemy 120 szt. XYZ-300 w ciągu tygodnia. "
    "Interesuje nas wyłącznie oryginalny produkt — nie akceptujemy zamienników.\n\n"
    "Proszę o potwierdzenie dostępności i cenę.\n\n"
    "Z poważaniem,\nEwa Kamińska\nZaopatrzenie, Technika Omega",
    date(2026, 11, 5),
)


@pytest.mark.parametrize(
    ("inquiry", "expected"),
    [
        (
            ACME,
            {
                "customer": "ACME Sp. z o.o.",
                "product_code": "ABC-100",
                "quantity": 80,
                "deadline_text": "do piątku",
                "deadline_date": "2026-11-06",
                "substitute_allowed": True,
                "price_kind": "best_price",
                "price_value": None,
                "price_text": "najlepszą cenę",
            },
        ),
        (
            BIURO_MAX,
            {
                "customer": "Biuro Max",
                "product_code": "ABC-200",
                "quantity": 20,
                "deadline_text": "do końca miesiąca",
                "deadline_date": "2026-11-30",
                "substitute_allowed": None,
                "price_kind": "none",
                "price_value": None,
                "price_text": None,
            },
        ),
        (
            DELTA,
            {
                "customer": "Hurtownia Delta",
                "product_code": "ABC-100",
                "quantity": 500,
                "deadline_text": None,
                "deadline_date": None,
                "substitute_allowed": None,
                "price_kind": "discount_percent",
                "price_value": 25.0,
                "price_text": "rabat 25%",
            },
        ),
        (
            OMEGA,
            {
                "customer": "Technika Omega",
                "product_code": "XYZ-300",
                "quantity": 120,
                "deadline_text": "w ciągu tygodnia",
                "deadline_date": "2026-11-12",
                "substitute_allowed": False,
                "price_kind": "none",
                "price_value": None,
                "price_text": None,
            },
        ),
    ],
    ids=["acme", "biuro-max", "delta", "omega"],
)
def test_rule_based_extractor_reads_seed_inquiries(
    inquiry: tuple[str, str, date], expected: dict[str, object]
) -> None:
    subject, body, reference = inquiry

    result = RuleBasedExtractor().extract(subject, body, reference)

    assert result.usage is None
    assert result.extraction.model_dump(exclude={"uncertain"}) == expected
    assert result.extraction.uncertain == []


def test_rule_based_extractor_falls_back_to_subject_and_tolerates_empty_body() -> None:
    result = RuleBasedExtractor().extract("Zamówienie: 5 szt. QW-12 na jutro", "", REFERENCE)

    assert result.extraction.quantity == 5
    assert result.extraction.product_code == "QW-12"
    assert result.extraction.deadline_text == "jutro"
    assert result.extraction.customer is None


# --- OpenAI-compatible client ---------------------------------------------------------

USAGE = {"prompt_tokens": 812, "completion_tokens": 143, "total_tokens": 955, "queue_time": 0.01}
VALID_CONTENT = {
    "customer": "ACME Sp. z o.o.",
    "product_code": "ABC-100",
    "quantity": 80,
    "deadline_text": "do piątku",
    "deadline_date": "2026-11-06",
    "substitute_allowed": True,
    "price_kind": "best_price",
    "price_value": None,
    "price_text": "najlepszą cenę",
    "uncertain": [{"field": "customer", "reason": "Signature only"}],
}


def _completion(content: object, usage: object = USAGE) -> dict[str, Any]:
    text = content if isinstance(content, str) else json.dumps(content)
    return {
        "id": "chatcmpl-1",
        "model": GROQ_MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
        "usage": usage,
    }


def _extractor(handler: Any) -> OpenAICompatibleExtractor:
    return OpenAICompatibleExtractor(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key="test-key",
        model=GROQ_MODEL,
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )


def test_openai_compatible_success_sends_strict_schema_and_maps_usage() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_completion(VALID_CONTENT))

    subject, body, _ = ACME
    result = _extractor(handler).extract(subject, body + "x" * (2 * MAX_BODY_CHARS), REFERENCE)

    (request,) = requests
    assert request.method == "POST"
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.content)
    assert payload["model"] == GROQ_MODEL
    assert payload["temperature"] == 0
    assert payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "inquiry_extraction",
            "strict": True,
            "schema": model_extraction_json_schema(),
        },
    }
    system, user = payload["messages"]
    assert system["role"] == "system"
    assert "2026-11-02 (poniedziałek)" in system["content"]
    assert user["role"] == "user"
    assert subject in user["content"]
    assert "x" * (MAX_BODY_CHARS + 1) not in user["content"]

    assert result.extraction == ModelExtraction.model_validate(VALID_CONTENT)
    assert result.usage == LlmUsage(
        provider="groq", model=GROQ_MODEL, input_tokens=812, output_tokens=143, raw=USAGE
    )
    assert price_usage(result.usage).status == "priced"


def test_openai_compatible_rate_limit() -> None:
    extractor = _extractor(lambda request: httpx.Response(429, json={"error": "slow down"}))

    with pytest.raises(ExtractionRateLimited):
        extractor.extract(*ACME)


def test_openai_compatible_server_error() -> None:
    extractor = _extractor(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(ExtractionFailed) as raised:
        extractor.extract(*ACME)

    assert raised.value.usage is None


def test_openai_compatible_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ExtractionFailed, match="timed out"):
        _extractor(handler).extract(*ACME)


def test_openai_compatible_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ExtractionFailed):
        _extractor(handler).extract(*ACME)


def test_openai_compatible_body_not_json() -> None:
    extractor = _extractor(lambda request: httpx.Response(200, text="<html>"))

    with pytest.raises(ExtractionFailed):
        extractor.extract(*ACME)


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        {**VALID_CONTENT, "quantity": "eighty"},
        {**VALID_CONTENT, "unexpected": 1},
        {key: value for key, value in VALID_CONTENT.items() if key != "uncertain"},
    ],
    ids=["not-json", "wrong-type", "extra-field", "missing-field"],
)
def test_openai_compatible_invalid_content_carries_usage(content: object) -> None:
    extractor = _extractor(lambda request: httpx.Response(200, json=_completion(content)))

    with pytest.raises(ExtractionFailed) as raised:
        extractor.extract(*ACME)

    assert raised.value.usage is not None
    assert raised.value.usage.input_tokens == 812
    assert raised.value.usage.output_tokens == 143
    assert raised.value.__cause__ is None  # no chained ValidationError quoting the inquiry


def test_openai_compatible_missing_message_carries_usage() -> None:
    body = {"choices": [], "usage": USAGE}
    extractor = _extractor(lambda request: httpx.Response(200, json=body))

    with pytest.raises(ExtractionFailed) as raised:
        extractor.extract(*ACME)

    assert raised.value.usage is not None


def test_openai_compatible_without_usage_still_extracts() -> None:
    extractor = _extractor(
        lambda request: httpx.Response(200, json=_completion(VALID_CONTENT, usage=None))
    )

    assert extractor.extract(*ACME).usage is None


# --- Strict schema --------------------------------------------------------------------


def _objects(node: object) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            found.append(node)
        for value in node.values():
            found.extend(_objects(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_objects(item))
    return found


def test_model_schema_meets_strict_rules() -> None:
    schema = model_extraction_json_schema()
    objects = _objects(schema)

    assert len(objects) == 2  # the extraction and an uncertain item
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert sorted(obj["required"]) == sorted(obj["properties"])
    assert "$ref" not in json.dumps(schema)
    assert schema["properties"]["customer"] == {"type": ["string", "null"]}
    assert schema["properties"]["price_kind"]["enum"] == [
        "none",
        "best_price",
        "discount_percent",
        "target_price",
    ]


# --- Selection from settings ----------------------------------------------------------


def test_get_extractor_defaults_to_rule_based() -> None:
    extractor = get_extractor(Settings(llm_provider="fake"))

    assert isinstance(extractor, RuleBasedExtractor)
    assert extractor.name == "fake"
    assert extractor.step_kind == "deterministic"


@pytest.mark.parametrize("provider", ["groq", "openrouter"])
def test_get_extractor_without_key_is_not_configured(provider: str) -> None:
    extractor = get_extractor(
        Settings.model_validate({"llm_provider": provider, "llm_api_key": ""})
    )

    assert isinstance(extractor, UnconfiguredExtractor)
    assert extractor.name == provider
    with pytest.raises(ExtractionNotConfigured):
        extractor.extract(*ACME)


@pytest.mark.parametrize(
    ("provider", "model", "expected_model"),
    [
        ("groq", None, GROQ_MODEL),
        ("openrouter", "", "nvidia/nemotron-3.5-super-vl:free"),
        ("groq", "openai/gpt-oss-20b", "openai/gpt-oss-20b"),
    ],
)
def test_get_extractor_with_key_uses_provider_default_model(
    provider: str, model: str | None, expected_model: str
) -> None:
    settings = Settings.model_validate(
        {"llm_provider": provider, "llm_api_key": SecretStr("k"), "llm_model": model}
    )

    extractor = get_extractor(settings)

    assert isinstance(extractor, OpenAICompatibleExtractor)
    assert extractor.name == provider
    assert extractor.step_kind == "llm"
    assert extractor.model == expected_model
