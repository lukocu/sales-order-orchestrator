from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import create_engine

from app.settings import get_settings

CONNECT_TIMEOUT_SECONDS = 3


def build_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


@lru_cache
def get_engine() -> Engine:
    """Process-wide engine singleton; also a FastAPI dependency overridable in tests."""
    return build_engine(get_settings().database_url)
