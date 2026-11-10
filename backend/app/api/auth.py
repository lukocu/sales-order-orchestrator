import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser, database_unavailable, get_current_user, session_cookie
from app.auth.models import User
from app.auth.passwords import verify_password
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


@router.post("/login", response_model=AuthUser)
def login(
    credentials: LoginRequest,
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> AuthUser:
    try:
        with Session(engine) as session:
            user = session.exec(
                select(User).where(col(User.username) == credentials.username)
            ).first()
            # Always verify (a dummy hash when there is no user or no password), so the
            # response time does not reveal whether the account exists.
            password_hash = user.password_hash if user is not None else None
            if user is None or not verify_password(credentials.password, password_hash):
                raise _invalid_credentials()
            auth_user = AuthUser.from_user(user)
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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Depends(session_cookie)],
    response: Response,
) -> None:
    """End the session (if any) and always clear the cookie."""
    if token:
        try:
            with Session(engine) as session:
                delete_session(session, token)
        except SQLAlchemyError:
            logger.exception("Logout: database unavailable")
            raise database_unavailable() from None
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.get("/me", response_model=AuthUser)
def me(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    return user
