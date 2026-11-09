from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint
from sqlmodel import Field, SQLModel

Role = Literal["salesperson", "supervisor"]

# Enum-like columns are VARCHAR with a CHECK constraint; the Literal type above mirrors it.
ROLE_LENGTH = 20


def _now() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        CheckConstraint("role IN ('salesperson', 'supervisor')", name="ck_users_role"),
    )

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(max_length=50)
    display_name: str = Field(max_length=100)
    role: Role = Field(sa_type=String(ROLE_LENGTH))
    # NULL means the account cannot log in (e.g. DEMO_PASSWORD is not set).
    password_hash: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=_now, sa_type=DateTime(timezone=True))


class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    # Hex SHA-256 of the cookie token; the raw token is never stored.
    token_hash: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=_now, sa_type=DateTime(timezone=True))
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))
