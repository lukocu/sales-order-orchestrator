import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from app.auth import demo_accounts
from app.auth.demo_accounts import sync_demo_passwords
from app.auth.models import User
from app.auth.passwords import verify_password
from tests.conftest import UserFactory, new_test_username

PASSWORD = "demo-test-password"


def _hash_of(engine: Engine, user: User) -> str | None:
    with Session(engine) as session:
        return session.get_one(User, user.id).password_hash


def test_sync_sets_a_hash_that_verifies(migrated_engine: Engine, make_user: UserFactory) -> None:
    user = make_user(password=None)

    sync_demo_passwords(migrated_engine, PASSWORD, usernames=[user.username])

    assert verify_password(PASSWORD, _hash_of(migrated_engine, user))


def test_sync_replaces_a_hash_of_another_password(
    migrated_engine: Engine, make_user: UserFactory
) -> None:
    user = make_user(password="old password")

    sync_demo_passwords(migrated_engine, PASSWORD, usernames=[user.username])

    assert verify_password(PASSWORD, _hash_of(migrated_engine, user))


def test_sync_keeps_a_matching_hash(migrated_engine: Engine, make_user: UserFactory) -> None:
    user = make_user(password=PASSWORD)
    before = _hash_of(migrated_engine, user)

    sync_demo_passwords(migrated_engine, PASSWORD, usernames=[user.username])

    assert _hash_of(migrated_engine, user) == before


def test_sync_without_password_clears_the_hash(
    migrated_engine: Engine, make_user: UserFactory
) -> None:
    user = make_user(password=PASSWORD)

    sync_demo_passwords(migrated_engine, None, usernames=[user.username])

    assert _hash_of(migrated_engine, user) is None


def test_sync_only_touches_listed_accounts(migrated_engine: Engine, make_user: UserFactory) -> None:
    listed = make_user(password=None)
    other = make_user(password=None)

    sync_demo_passwords(migrated_engine, PASSWORD, usernames=[listed.username])

    assert _hash_of(migrated_engine, other) is None


def test_sync_skips_missing_accounts(migrated_engine: Engine, delete_test_rows: None) -> None:
    sync_demo_passwords(migrated_engine, PASSWORD, usernames=[new_test_username()])


def test_main_exits_zero_when_the_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch, unreachable_engine: Engine
) -> None:
    monkeypatch.setattr(demo_accounts, "get_engine", lambda: unreachable_engine)

    assert demo_accounts.main() == 0
