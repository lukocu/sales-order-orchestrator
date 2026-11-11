"""One POST to an OpenAI-compatible `/chat/completions`, its `usage` and error classes.

Used by the inquiry parser and the orchestration planner. Error messages carry the provider
name and the status or error class only, never the request or the provider's response body.
"""

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from app.settings import LlmProvider
from app.tracing.pricing import LlmUsage

# Model ids as genai-prices knows them: without the `openai/` prefix Groq is unpriced.
DEFAULT_MODELS: dict[LlmProvider, str] = {
    "groq": "openai/gpt-oss-120b",
    "openrouter": "nvidia/nemotron-3.5-super-vl:free",
}
BASE_URLS: dict[LlmProvider, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


@dataclass(frozen=True)
class ChatResult:
    content: str  # the message content, not yet parsed
    usage: LlmUsage | None  # None when the provider sent no (readable) usage


class LlmError(Exception):
    """The call did not produce message content.

    `usage` is set when the provider answered (and billed) before the failure.
    """

    def __init__(self, message: str, *, usage: LlmUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class LlmRateLimited(LlmError):
    """The provider answered 429."""


class LlmHttpError(LlmError):
    """The provider answered another non-success status."""

    def __init__(self, message: str, *, status_code: int, usage: LlmUsage | None = None) -> None:
        super().__init__(message, usage=usage)
        self.status_code = status_code


class LlmTimeout(LlmError):
    """The request timed out."""


class LlmNetworkError(LlmError):
    """The request failed before an answer (connection, protocol)."""


class LlmBadResponse(LlmError):
    """The answer is not JSON or has no message content."""


def chat_json(
    *,
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: float,
    payload: dict[str, Any],
    transport: httpx.BaseTransport | None = None,
) -> ChatResult:
    """POST `payload` and return the first message's content with the call's usage.

    `name` is the provider (also the genai-prices provider id) and `model` the model id the
    usage is priced with.
    """
    response = _post(name, base_url, api_key, timeout_seconds, payload, transport)
    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        raise LlmRateLimited(f"{name} rate limit reached")
    if not response.is_success:
        raise LlmHttpError(
            f"{name} answered HTTP {response.status_code}", status_code=response.status_code
        )
    try:
        data = response.json()
    except ValueError as error:
        raise LlmBadResponse(f"{name} answered with invalid JSON") from error
    # Usage first: the call is billed even when its content turns out to be unusable.
    usage = _usage(name, model, data)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LlmBadResponse(f"{name} response has no message content", usage=usage) from error
    if not isinstance(content, str):
        raise LlmBadResponse(f"{name} response has no message content", usage=usage)
    return ChatResult(content=content, usage=usage)


def _post(
    name: str,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    payload: dict[str, Any],
    transport: httpx.BaseTransport | None,
) -> httpx.Response:
    try:
        with httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        ) as client:
            return client.post("/chat/completions", json=payload)
    except httpx.TimeoutException as error:
        raise LlmTimeout(f"{name} timed out") from error
    except httpx.HTTPError as error:
        raise LlmNetworkError(f"{name} request failed: {type(error).__name__}") from error


def _usage(name: str, model: str, data: Any) -> LlmUsage | None:
    raw = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None
    try:
        return LlmUsage(
            provider=name,
            model=model,
            input_tokens=raw["prompt_tokens"],
            output_tokens=raw["completion_tokens"],
            raw=raw,
        )
    except KeyError, ValidationError:
        return None
