import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import AwareDatetime, BaseModel, ConfigDict
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.api.errors import database_unavailable
from app.auth.deps import AuthUser, get_current_user
from app.db import get_engine
from app.parsing.extractor import (
    ExtractionError,
    ExtractionNotConfigured,
    ExtractionRateLimited,
    InquiryExtractor,
    get_extractor,
)
from app.parsing.schema import FieldName, ParsedFields
from app.parsing.service import (
    AnalysisChanged,
    AnalysisNotFound,
    AnalysisView,
    InquiryNotFound,
    analyze_inquiry,
    get_analysis,
    save_corrections,
)

logger = logging.getLogger(__name__)

router = APIRouter()

PATH = "/inquiries/{inquiry_id}/analysis"
# inquiries.id is a Postgres int4; out-of-range ids are a 422, not a driver error.
InquiryId = Annotated[int, Path(ge=1, le=2_147_483_647)]


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: ParsedFields
    reviewed: list[FieldName]  # uncertain fields the user confirmed without changing
    analyzed_at: AwareDatetime  # of the analysis the corrections were made on


def _inquiry_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found")


def _extraction_error(error: ExtractionError) -> HTTPException:
    if isinstance(error, ExtractionNotConfigured):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM not configured"
        )
    if isinstance(error, ExtractionRateLimited):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM rate limit reached, try again later",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY, detail="Analysis failed, try again"
    )


@router.get(PATH, response_model=AnalysisView | None)
def read_analysis(
    inquiry_id: InquiryId, engine: Annotated[Engine, Depends(get_engine)]
) -> AnalysisView | None:
    """The current analysis, or `null` when the inquiry has not been analyzed yet."""
    try:
        return get_analysis(engine, inquiry_id)
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None


@router.post(PATH, response_model=AnalysisView)
def analyze(
    inquiry_id: InquiryId,
    engine: Annotated[Engine, Depends(get_engine)],
    extractor: Annotated[InquiryExtractor, Depends(get_extractor)],
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AnalysisView:
    """Analyze the inquiry, replacing its analysis and corrections; on failure nothing changes."""
    try:
        return analyze_inquiry(engine, extractor, inquiry_id, user)
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except ExtractionError as error:
        # Class and inquiry id only: neither the message nor a traceback reaches the log,
        # so no inquiry content can.
        logger.warning(
            "Analysis API: extraction failed for inquiry %s: %s",
            inquiry_id,
            type(error).__name__,
        )
        raise _extraction_error(error) from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None


@router.put(PATH, response_model=AnalysisView)
def correct(
    inquiry_id: InquiryId,
    corrections: CorrectionRequest,
    engine: Annotated[Engine, Depends(get_engine)],
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AnalysisView:
    """Save the user's field values; 409 when the analysis was replaced in the meantime."""
    try:
        return save_corrections(
            engine,
            inquiry_id,
            corrections.fields,
            corrections.reviewed,
            corrections.analyzed_at,
            user,
        )
    except AnalysisNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No analysis yet"
        ) from None
    except AnalysisChanged:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Analysis changed, reload"
        ) from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
