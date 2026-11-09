import logging
from typing import Annotated, Literal

from alembic.runtime.migration import MigrationContext
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_engine

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    migration: str | None


@router.get("/health", response_model=HealthResponse)
def health(
    engine: Annotated[Engine, Depends(get_engine)],
    response: Response,
) -> HealthResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            # Reads alembic_version; returns None when the table does not exist yet.
            revision = MigrationContext.configure(connection).get_current_revision()
    except SQLAlchemyError:
        logger.exception("Health check: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="error", migration=None)
    return HealthResponse(status="ok", database="ok", migration=revision)
