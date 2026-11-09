from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

RunStatus = Literal["running", "completed", "failed"]
StepKind = Literal["deterministic", "llm"]
StepStatus = Literal["ok", "failed"]
PriceStatus = Literal["priced", "unpriced", "not_applicable"]

# Enum-like columns are VARCHAR with a CHECK constraint; the Literal types above mirror them.
ENUM_LENGTH = 20


class TraceRun(SQLModel, table=True):
    __tablename__ = "trace_runs"
    __table_args__ = (
        Index("ix_trace_runs_subject", "subject_type", "subject_id"),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')", name="ck_trace_runs_status"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    subject_type: str = Field(max_length=50)  # e.g. inquiry, eval, demo
    subject_id: str = Field(max_length=100)
    status: RunStatus = Field(sa_type=String(ENUM_LENGTH))
    started_at: datetime = Field(sa_type=DateTime(timezone=True))
    duration_us: int | None = Field(default=None, sa_type=BigInteger)  # set on finish


class TraceStep(SQLModel, table=True):
    __tablename__ = "trace_steps"
    __table_args__ = (
        CheckConstraint("kind IN ('deterministic', 'llm')", name="ck_trace_steps_kind"),
        CheckConstraint("status IN ('ok', 'failed')", name="ck_trace_steps_status"),
        CheckConstraint(
            "price_status IN ('priced', 'unpriced', 'not_applicable')",
            name="ck_trace_steps_price_status",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="trace_runs.id", ondelete="CASCADE", index=True)
    name: str = Field(max_length=100)
    kind: StepKind = Field(sa_type=String(ENUM_LENGTH))
    status: StepStatus = Field(sa_type=String(ENUM_LENGTH))
    # Exception class name only, never the message.
    error_type: str | None = Field(default=None, max_length=200)
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
    # input_tokens includes cache_read_tokens and cache_write_tokens.
    input_tokens: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    output_tokens: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    cache_read_tokens: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    cache_write_tokens: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    cost_usd: Decimal | None = Field(default=None, sa_type=Numeric(16, 10))
    price_status: PriceStatus = Field(sa_type=String(ENUM_LENGTH))
    price_source: str | None = Field(default=None, max_length=100)  # e.g. genai-prices 0.2.1
    raw_usage: dict[str, Any] | None = Field(default=None, sa_type=JSONB)
    started_at: datetime = Field(sa_type=DateTime(timezone=True))
    duration_us: int = Field(sa_type=BigInteger)
