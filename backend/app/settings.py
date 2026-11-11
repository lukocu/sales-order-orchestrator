from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

LlmProvider = Literal["fake", "groq", "openrouter"]


def normalize_database_url(url: str) -> str:
    """Make a plain Postgres URL (compose, Supabase) use the psycopg 3 driver."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Later files win; a missing file is ignored, real env vars override both.
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    # Default targets the local compose `db` service; deployments set DATABASE_URL.
    database_url: str = "postgresql://postgres:postgres@localhost:5432/orchestrator"

    # Built frontend (Vite dist). The Docker image copies it here; when the directory
    # does not exist (dev, tests) the app serves the API only.
    static_dir: Path = BACKEND_DIR / "static"

    # Shared password of the demo accounts (sales, supervisor), applied on start by
    # `python -m app.auth.demo_accounts`. Unset or empty: demo login is disabled.
    demo_password: SecretStr | None = None

    # `Secure` flag of the session cookie. Local compose sets it to false, because
    # Safari rejects Secure cookies on http://localhost.
    cookie_secure: bool = True

    # Inquiry analysis, orchestration planning and recommendation: `fake` is the rule-based
    # parser, planner and recommender (no key, no network); `groq` and `openrouter` call an
    # OpenAI-compatible endpoint with LLM_API_KEY. LLM_MODEL unset or empty: the provider's
    # default model (see app.llm.client.DEFAULT_MODELS).
    llm_provider: LlmProvider = "fake"
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=30, gt=0)

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("demo_password", "llm_api_key", "llm_model", mode="before")
    @classmethod
    def _empty_string_is_unset(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
