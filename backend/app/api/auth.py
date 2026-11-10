import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.api.errors import database_unavailable
from app.auth.deps import AuthUser, get_current_user, session_cookie
from app.auth.models import User
from app.auth.passwords import LOGIN_VERIFY_SLOTS, LOGIN_VERIFY_WAIT_SECONDS, verify_password
from app.auth.sessions import SESSION_COOKIE, SESSION_TTL, create_session, delete_session
from app.db import get_engine
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
    )


def _login_busy() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Login busy, try again"
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/login", response_model=AuthUser)
def login(
    credentials: LoginRequest,
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    previous_token: Annotated[str | None, Depends(session_cookie)],
    response: Response,
) -> AuthUser:
    # Short database sessions on both sides of the slow password check, so a login
    # never holds a pooled connection while Argon2 runs.
    try:
        with Session(engine) as session:
            user = session.exec(
                select(User).where(col(User.username) == credentials.username)
            ).first()
            auth_user = AuthUser.from_user(user) if user is not None else None
            password_hash = user.password_hash if user is not None else None
    except SQLAlchemyError:
        logger.exception("Login: database unavailable")
        raise database_unavailable() from None
    if not LOGIN_VERIFY_SLOTS.acquire(timeout=LOGIN_VERIFY_WAIT_SECONDS):
        raise _login_busy()
    try:
        # Always verify (a dummy hash when there is no user or no password), so the
        # response time does not reveal whether the account exists.
        password_ok = verify_password(credentials.password, password_hash)
    finally:
        LOGIN_VERIFY_SLOTS.release()
    if auth_user is None or not password_ok:
        raise _invalid_credentials()
    try:
        with Session(engine) as session:
            # The browser's previous session ends with this login (e.g. switching accounts).
            if previous_token:
                delete_session(session, previous_token)
            token = create_session(session, auth_user.id)
    except SQLAlchemyError:
        logger.exception("Login: database unavailable")
        raise database_unavailable() from None
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return auth_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def logout(
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Depends(session_cookie)],
    response: Response,
) -> JSONResponse | None:
    """End the session (if any) and always clear the cookie, even when the database fails."""
    if token:
        try:
            with Session(engine) as session:
                delete_session(session, token)
        except SQLAlchemyError:
            logger.exception("Logout: database unavailable")
            error = database_unavailable()
            error_response = JSONResponse(
                status_code=error.status_code, content={"detail": error.detail}
            )
            _clear_session_cookie(error_response, settings)
            return error_response
    _clear_session_cookie(response, settings)
    return None


@router.get("/me", response_model=AuthUser)
def me(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    return user
