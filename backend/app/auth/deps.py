import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.auth.models import Role, User
from app.auth.sessions import SESSION_COOKIE, get_session_user
from app.db import get_engine

logger = logging.getLogger(__name__)

# Declared as a security scheme so the session cookie shows up in /docs.
session_cookie = APIKeyCookie(name=SESSION_COOKIE, auto_error=False)


class AuthUser(BaseModel):
    id: int
    username: str
    display_name: str
    role: Role

    @classmethod
    def from_user(cls, user: User) -> AuthUser:
        assert user.id is not None
        return cls(
            id=user.id, username=user.username, display_name=user.display_name, role=user.role
        )


def not_authenticated() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def database_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
    )


def get_current_user(
    engine: Annotated[Engine, Depends(get_engine)],
    token: Annotated[str | None, Depends(session_cookie)],
) -> AuthUser:
    """The logged-in user; 401 without a valid session (no database access without a cookie)."""
    if not token:
        raise not_authenticated()
    try:
        with Session(engine) as session:
            user = get_session_user(session, token)
            auth_user = AuthUser.from_user(user) if user is not None else None
    except SQLAlchemyError:
        logger.exception("Auth: database unavailable")
        raise database_unavailable() from None
    if auth_user is None:
        raise not_authenticated()
    return auth_user
