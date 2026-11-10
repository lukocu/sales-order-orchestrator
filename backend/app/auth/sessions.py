"""Login sessions: the cookie holds a random token, the database only its SHA-256."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.auth.models import User, UserSession

SESSION_COOKIE = "session"
SESSION_TTL = timedelta(days=7)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(session: Session, user_id: int) -> str:
    """Store a new session for `user_id` and return its raw token (for the cookie).

    Also deletes the user's expired sessions, so the table does not grow without bound.
    """
    now = datetime.now(UTC)
    session.exec(
        delete(UserSession).where(
            col(UserSession.user_id) == user_id, col(UserSession.expires_at) <= now
        )
    )
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            user_id=user_id,
            token_hash=_hash_token(token),
            created_at=now,
            expires_at=now + SESSION_TTL,
        )
    )
    session.commit()
    return token


def get_session_user(session: Session, token: str) -> User | None:
    """The user of a valid session; None for an unknown or expired token."""
    statement = (
        select(User)
        .join(UserSession, col(UserSession.user_id) == col(User.id))
        .where(
            col(UserSession.token_hash) == _hash_token(token),
            col(UserSession.expires_at) > datetime.now(UTC),
        )
    )
    return session.exec(statement).first()


def delete_session(session: Session, token: str) -> None:
    session.exec(delete(UserSession).where(col(UserSession.token_hash) == _hash_token(token)))
    session.commit()
