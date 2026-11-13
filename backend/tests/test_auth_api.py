from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update
from sqlmodel import Session, col

from app.api import auth as auth_api
from app.auth.deps import AuthUser, require_supervisor
from app.auth.models import Role, User, UserSession
from app.auth.passwords import LOGIN_VERIFY_SLOTS, verify_password
from app.main import app
from app.settings import get_settings
from tests.conftest import TEST_PASSWORD, UserFactory, new_test_username

INVALID_CREDENTIALS = {"detail": "Invalid username or password"}
NOT_AUTHENTICATED = {"detail": "Not authenticated"}
DATABASE_UNAVAILABLE = {"detail": "Database unavailable"}


def _credentials(username: str, password: str = TEST_PASSWORD) -> dict[str, str]:
    return {"username": username, "password": password}


def _cookie_attributes(set_cookie: str) -> tuple[str, set[str]]:
    """The cookie's `name=value` and its lower-cased attributes."""
    name_value, *attributes = set_cookie.split("; ")
    return name_value, {attribute.lower() for attribute in attributes}


@pytest.mark.parametrize("secure", [True, False])
def test_login_returns_user_and_session_cookie(
    client: TestClient, test_user: User, secure: bool
) -> None:
    # Compose sets COOKIE_SECURE=false and CI keeps the default, so pin it here.
    settings = get_settings().model_copy(update={"cookie_secure": secure})
    app.dependency_overrides[get_settings] = lambda: settings

    response = client.post("/api/auth/login", json=_credentials(test_user.username))

    assert response.status_code == 200
    assert response.json() == {
        "id": test_user.id,
        "username": test_user.username,
        "display_name": test_user.display_name,
        "role": test_user.role,
    }
    name_value, attributes = _cookie_attributes(response.headers["set-cookie"])
    assert name_value.startswith("session=") and len(name_value) > len("session=")
    assert {"httponly", "samesite=lax", "path=/", "max-age=604800"} <= attributes
    assert ("secure" in attributes) is secure


@pytest.mark.parametrize("password", [TEST_PASSWORD + "-wrong", "x"])
def test_wrong_password_is_401(client: TestClient, test_user: User, password: str) -> None:
    response = client.post("/api/auth/login", json=_credentials(test_user.username, password))

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS
    assert "set-cookie" not in response.headers


def test_unknown_username_is_401(client: TestClient) -> None:
    response = client.post("/api/auth/login", json=_credentials(new_test_username()))

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS


def test_unknown_username_still_verifies_a_password(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str | None] = []

    def spy(password: str, password_hash: str | None) -> bool:
        calls.append(password_hash)
        return verify_password(password, password_hash)

    monkeypatch.setattr(auth_api, "verify_password", spy)

    response = client.post("/api/auth/login", json=_credentials(new_test_username()))

    assert response.status_code == 401
    assert calls == [None]


def test_login_is_503_when_all_verification_slots_are_busy(
    client: TestClient, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_api, "LOGIN_VERIFY_WAIT_SECONDS", 0.01)
    held = 0
    try:
        while LOGIN_VERIFY_SLOTS.acquire(blocking=False):
            held += 1
        response = client.post("/api/auth/login", json=_credentials(test_user.username))
    finally:
        for _ in range(held):
            LOGIN_VERIFY_SLOTS.release()

    assert response.status_code == 503
    assert response.json() == {"detail": "Login busy, try again"}
    assert "set-cookie" not in response.headers


def test_login_without_database_is_503(client_without_db: TestClient) -> None:
    response = client_without_db.post("/api/auth/login", json=_credentials(new_test_username()))

    assert response.status_code == 503
    assert response.json() == DATABASE_UNAVAILABLE


def test_login_ends_the_previous_session(auth_client: TestClient, test_user: User) -> None:
    old_token = auth_client.cookies["session"]

    response = auth_client.post("/api/auth/login", json=_credentials(test_user.username))

    assert response.status_code == 200
    new_token = auth_client.cookies["session"]
    assert new_token != old_token
    assert auth_client.get("/api/auth/me").status_code == 200
    auth_client.cookies.clear()
    auth_client.cookies.set("session", old_token)
    assert auth_client.get("/api/auth/me").status_code == 401


def test_account_without_password_is_401(client: TestClient, make_user: UserFactory) -> None:
    user = make_user(password=None)

    response = client.post("/api/auth/login", json=_credentials(user.username))

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS


def test_me_without_session_is_401(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


def test_me_with_session_returns_user(auth_client: TestClient, test_user: User) -> None:
    response = auth_client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == test_user.username


def test_logout_ends_the_session(auth_client: TestClient) -> None:
    token = auth_client.cookies["session"]

    response = auth_client.post("/api/auth/logout")

    assert response.status_code == 204
    name_value, attributes = _cookie_attributes(response.headers["set-cookie"])
    assert name_value in {"session=", 'session=""'}
    assert {"httponly", "samesite=lax", "path=/", "max-age=0"} <= attributes
    auth_client.cookies.clear()
    auth_client.cookies.set("session", token)
    assert auth_client.get("/api/auth/me").status_code == 401


def test_logout_without_session_is_204(client: TestClient) -> None:
    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert "max-age=0" in _cookie_attributes(response.headers["set-cookie"])[1]


def test_logout_without_database_is_503_and_clears_the_cookie(
    client_without_db: TestClient,
) -> None:
    client_without_db.cookies.set("session", "some-token")

    response = client_without_db.post("/api/auth/logout")

    assert response.status_code == 503
    assert response.json() == DATABASE_UNAVAILABLE
    name_value, attributes = _cookie_attributes(response.headers["set-cookie"])
    assert name_value in {"session=", 'session=""'}
    assert {"httponly", "samesite=lax", "path=/", "max-age=0"} <= attributes


def test_expired_session_is_401(
    auth_client: TestClient, test_user: User, migrated_engine: Engine
) -> None:
    with Session(migrated_engine) as session:
        session.exec(
            update(UserSession)
            .where(col(UserSession.user_id) == test_user.id)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        session.commit()

    response = auth_client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200


def test_unknown_api_path_without_session_is_json_404(client: TestClient) -> None:
    response = client.get("/api/nieistnieje")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize(("role", "allowed"), [("supervisor", True), ("salesperson", False)])
def test_require_supervisor_checks_the_role(role: Role, allowed: bool) -> None:
    user = AuthUser(id=1, username="someone", display_name="Someone", role=role)

    if allowed:
        assert require_supervisor(user) == user
    else:
        with pytest.raises(HTTPException) as raised:
            require_supervisor(user)
        assert (raised.value.status_code, raised.value.detail) == (403, "Supervisor role required")


def test_supervisor_only_endpoint_without_session_is_401(client: TestClient) -> None:
    response = client.post("/api/inquiries/1/draft/supervisor-decision", json={})

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


def test_supervisor_only_endpoint_is_403_for_a_salesperson(auth_client: TestClient) -> None:
    # The role is checked before the body or the inquiry is looked at.
    response = auth_client.post("/api/inquiries/1/draft/supervisor-decision", json={})

    assert response.status_code == 403
    assert response.json() == {"detail": "Supervisor role required"}
