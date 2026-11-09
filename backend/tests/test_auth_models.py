from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.auth.models import User
from app.auth.passwords import hash_password, verify_password
from tests.conftest import new_test_username

PASSWORD = "correct horse battery staple"


def test_hash_is_not_the_password_and_verifies() -> None:
    password_hash = hash_password(PASSWORD)

    assert PASSWORD not in password_hash
    assert verify_password(PASSWORD, password_hash) is True


def test_wrong_password_does_not_verify() -> None:
    assert verify_password("wrong password", hash_password(PASSWORD)) is False


def test_missing_hash_never_verifies() -> None:
    assert verify_password(PASSWORD, None) is False


def test_unrecognized_hash_never_verifies() -> None:
    assert verify_password(PASSWORD, "not-a-hash") is False


def test_role_check_rejects_unknown_role(migrated_engine: Engine, delete_test_rows: None) -> None:
    statement = insert(User).values(
        username=new_test_username(),
        display_name="Test User",
        role="admin",
        created_at=datetime.now(UTC),
    )

    with Session(migrated_engine) as session, pytest.raises(IntegrityError, match="ck_users_role"):
        session.execute(statement)
        session.commit()
