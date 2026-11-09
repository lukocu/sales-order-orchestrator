from collections.abc import Iterator
from datetime import datetime
from typing import Protocol
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlmodel import Session, col

from app.auth.models import Role, User
from app.auth.passwords import hash_password
from app.db import build_engine, get_engine
from app.inquiries.models import Inquiry
from app.main import app
from app.settings import BACKEND_DIR, get_settings

UNREACHABLE_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/unreachable"

# Unique per pytest process, so teardowns delete only the rows this process created.
TEST_SUBJECT_TYPE = f"test-{uuid4().hex[:12]}"  # trace_runs.subject_type is VARCHAR(50)
# Test users are `<marker>-<hex>` (30 chars; users.username is VARCHAR(50)) and test
# inquiries are sent from `...@<marker>.test`; the demo accounts are never touched.
TEST_USERNAME_PREFIX = f"{TEST_SUBJECT_TYPE}-"
TEST_EMAIL_DOMAIN = f"{TEST_SUBJECT_TYPE}.test"


def new_test_username() -> str:
    return f"{TEST_USERNAME_PREFIX}{uuid4().hex[:12]}"


class UserFactory(Protocol):
    def __call__(self, *, role: Role = ..., password: str | None = ...) -> User: ...


class InquiryFactory(Protocol):
    def __call__(self, *, received_at: datetime, subject: str = ...) -> Inquiry: ...


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """Engine for the DATABASE_URL database after `alembic upgrade head`."""
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    engine = build_engine(get_settings().database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def unreachable_engine() -> Iterator[Engine]:
    engine = build_engine(UNREACHABLE_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def delete_test_rows(migrated_engine: Engine) -> Iterator[None]:
    """After the test, delete the test users (sessions cascade) and test inquiries."""
    yield
    with Session(migrated_engine) as session:
        session.exec(delete(User).where(col(User.username).startswith(TEST_USERNAME_PREFIX)))
        session.exec(
            delete(Inquiry).where(col(Inquiry.sender_email).endswith(f"@{TEST_EMAIL_DOMAIN}"))
        )
        session.commit()


def _add(engine: Engine, row: User | Inquiry) -> None:
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)


@pytest.fixture
def make_user(migrated_engine: Engine, delete_test_rows: None) -> UserFactory:
    """Create a test user; `password=None` leaves the hash NULL (cannot log in)."""

    def make(*, role: Role = "salesperson", password: str | None = None) -> User:
        user = User(
            username=new_test_username(),
            display_name="Test User",
            role=role,
            password_hash=hash_password(password) if password is not None else None,
        )
        _add(migrated_engine, user)
        return user

    return make


@pytest.fixture
def make_inquiry(migrated_engine: Engine, delete_test_rows: None) -> InquiryFactory:
    def make(*, received_at: datetime, subject: str = "Test inquiry") -> Inquiry:
        inquiry = Inquiry(
            sender_name="Test Sender",
            sender_email=f"sender-{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}",
            subject=subject,
            body="Test inquiry body.",
            received_at=received_at,
        )
        _add(migrated_engine, inquiry)
        return inquiry

    return make


def _client_with(engine: Engine) -> Iterator[TestClient]:
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(migrated_engine: Engine) -> Iterator[TestClient]:
    yield from _client_with(migrated_engine)


@pytest.fixture
def client_without_db(unreachable_engine: Engine) -> Iterator[TestClient]:
    yield from _client_with(unreachable_engine)
