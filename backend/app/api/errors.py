"""Stable HTTP error identifiers; presentation belongs to the client.

Codes are explicit at the source. No exception message or user input is used to
choose one, and no exception data is copied into translation parameters.
"""

import logging
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApiHTTPException(HTTPException):
    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        code: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


def error_body(error: ApiHTTPException) -> dict[str, Any]:
    return {"detail": error.detail, "code": error.code}


def database_unavailable() -> ApiHTTPException:
    return ApiHTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database unavailable",
        code="DATABASE_UNAVAILABLE",
    )


async def http_error_response(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)
    code = (
        error.code
        if isinstance(error, ApiHTTPException)
        else {
            401: "NOT_AUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            429: "RATE_LIMITED",
        }.get(error.status_code, "HTTP_ERROR")
    )
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail, "code": code},
        headers=error.headers,
    )


async def validation_error_response(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(error.errors()), "code": "VALIDATION_ERROR"},
    )


async def unexpected_error_response(_request: Request, error: Exception) -> JSONResponse:
    # Keep the original exception and traceback for server diagnostics.
    logger.error("Unhandled API error", exc_info=(type(error), error, error.__traceback__))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error", "code": "INTERNAL_ERROR"},
    )
