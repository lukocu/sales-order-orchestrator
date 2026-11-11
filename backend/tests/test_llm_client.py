import json
from typing import Any

import httpx
import pytest

from app.llm.client import (
    BASE_URLS,
    DEFAULT_MODELS,
    ChatResult,
    LlmBadResponse,
    LlmHttpError,
    LlmNetworkError,
    LlmRateLimited,
    LlmTimeout,
    chat_json,
)
from app.parsing import extractor
from app.tracing.pricing import LlmUsage

MODEL = "openai/gpt-oss-120b"
USAGE = {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}
PAYLOAD = {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}


def _chat(handler: Any) -> ChatResult:
    return chat_json(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key="test-key",
        model=MODEL,
        timeout_seconds=5,
        payload=PAYLOAD,
        transport=httpx.MockTransport(handler),
    )


def _completion(content: object, usage: object = USAGE) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": content}}], "usage": usage}


def test_success_posts_payload_and_maps_usage() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_completion('{"a": 1}'))

    result = _chat(handler)

    (request,) = requests
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert json.loads(request.content) == PAYLOAD
    assert result == ChatResult(
        content='{"a": 1}',
        usage=LlmUsage(provider="groq", model=MODEL, input_tokens=120, output_tokens=30, raw=USAGE),
    )


@pytest.mark.parametrize(
    "usage", [None, "n/a", {"prompt_tokens": 1}, {"prompt_tokens": -1, "completion_tokens": 1}]
)
def test_missing_or_unreadable_usage_is_none(usage: object) -> None:
    result = _chat(lambda request: httpx.Response(200, json=_completion("{}", usage=usage)))

    assert (result.content, result.usage) == ("{}", None)


def test_rate_limit() -> None:
    with pytest.raises(LlmRateLimited, match="groq rate limit reached") as raised:
        _chat(lambda request: httpx.Response(429, json={"error": "slow down"}))

    assert raised.value.usage is None


@pytest.mark.parametrize("status", [400, 401, 500, 503])
def test_http_error_carries_status_but_not_the_body(status: int) -> None:
    with pytest.raises(LlmHttpError) as raised:
        _chat(lambda request: httpx.Response(status, text="secret provider detail"))

    assert raised.value.status_code == status
    assert str(raised.value) == f"groq answered HTTP {status}"
    assert raised.value.usage is None


def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(LlmTimeout, match="groq timed out"):
        _chat(handler)


def test_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LlmNetworkError, match="groq request failed: ConnectError"):
        _chat(handler)


def test_body_not_json() -> None:
    with pytest.raises(LlmBadResponse) as raised:
        _chat(lambda request: httpx.Response(200, text="<html>"))

    assert raised.value.usage is None


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [], "usage": USAGE},
        {"choices": [{"message": {}}], "usage": USAGE},
        _completion(None),
        _completion({"a": 1}),
    ],
    ids=["no-choices", "no-content", "null-content", "object-content"],
)
def test_missing_content_carries_usage(body: dict[str, Any]) -> None:
    with pytest.raises(LlmBadResponse, match="no message content") as raised:
        _chat(lambda request: httpx.Response(200, json=body))

    assert raised.value.usage is not None
    assert (raised.value.usage.input_tokens, raised.value.usage.output_tokens) == (120, 30)


def test_provider_tables_are_re_exported_by_the_parser() -> None:
    assert extractor.BASE_URLS is BASE_URLS
    assert extractor.DEFAULT_MODELS is DEFAULT_MODELS
