import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.api.errors import ApiHTTPException, database_unavailable
from app.auth.deps import AuthUser, get_current_user, require_supervisor
from app.checks.service import NoAnalysis
from app.db import get_engine
from app.draft.drafter import Drafter, get_drafter
from app.draft.offer import InvalidEdit, LineEdit
from app.draft.service import (
    DraftChanged,
    DraftDecided,
    DraftNotEditable,
    DraftStale,
    NotAwaitingSupervisor,
    NothingToDraft,
    OwnSubmission,
    PolicyMissing,
    ReasonRequired,
)
from app.inquiries.mutations import AwaitingSupervisor, MutationConflict
from app.orchestration.planning import Planner, get_planner
from app.orchestration.service import NothingToOrchestrate
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
    decide_draft_inquiry,
    edit_draft_inquiry,
    get_analysis,
    recheck_inquiry,
    redraft_inquiry,
    reevaluate_policy_inquiry,
    reorchestrate_inquiry,
    rerecommend_inquiry,
    save_corrections,
    supervisor_decide_inquiry,
)
from app.policy.service import NothingToEvaluate
from app.recommendation.recommender import Recommender, get_recommender
from app.recommendation.service import NothingToRecommend

logger = logging.getLogger(__name__)

router = APIRouter()

PATH = "/inquiries/{inquiry_id}/analysis"
CHECKS_PATH = "/inquiries/{inquiry_id}/checks"
ORCHESTRATION_PATH = "/inquiries/{inquiry_id}/orchestration"
RECOMMENDATION_PATH = "/inquiries/{inquiry_id}/recommendation"
POLICY_PATH = "/inquiries/{inquiry_id}/policy"
DRAFT_PATH = "/inquiries/{inquiry_id}/draft"
DECISION_PATH = "/inquiries/{inquiry_id}/draft/decision"
SUPERVISOR_DECISION_PATH = "/inquiries/{inquiry_id}/draft/supervisor-decision"
# inquiries.id is a Postgres int4; out-of-range ids are a 422, not a driver error.
InquiryId = Annotated[int, Path(ge=1, le=2_147_483_647)]


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: ParsedFields
    reviewed: list[FieldName]  # uncertain fields the user confirmed without changing
    analyzed_at: AwareDatetime  # of the analysis the corrections were made on


def _mutation_conflict(error: MutationConflict) -> ApiHTTPException:
    code = "AWAITING_SUPERVISOR" if isinstance(error, AwaitingSupervisor) else "INQUIRY_CHANGED"
    return ApiHTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error), code=code)


def _inquiry_not_found() -> HTTPException:
    return ApiHTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found", code="INQUIRY_NOT_FOUND"
    )


def _no_analysis() -> HTTPException:
    return ApiHTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="No analysis yet", code="NO_ANALYSIS"
    )


def _invalid_stored_analysis() -> HTTPException:
    # A stored row no longer matching ParsedFields (schema changed without a data migration).
    # Only the class is logged: the validation message would quote the stored values.
    logger.error("Analysis API: stored analysis does not match the schema (ValidationError)")
    return ApiHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Stored analysis is invalid",
        code="STORED_ANALYSIS_INVALID",
    )


def _checks_failed(inquiry_id: int, error: Exception) -> HTTPException:
    # Class and inquiry id only: the message could quote inquiry content.
    logger.error("Analysis API: checks failed for inquiry %s: %s", inquiry_id, type(error).__name__)
    return ApiHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Checks failed",
        code="CHECKS_FAILED",
    )


def _orchestration_failed(inquiry_id: int, error: Exception) -> HTTPException:
    # Class and inquiry id only: the message could quote inquiry content.
    logger.error(
        "Analysis API: orchestration failed for inquiry %s: %s", inquiry_id, type(error).__name__
    )
    return ApiHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Orchestration failed",
        code="ORCHESTRATION_FAILED",
    )


def _recommendation_failed(inquiry_id: int, error: Exception) -> HTTPException:
    # Class and inquiry id only: the message could quote inquiry content.
    logger.error(
        "Analysis API: recommendation failed for inquiry %s: %s", inquiry_id, type(error).__name__
    )
    return ApiHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Recommendation failed",
        code="RECOMMENDATION_FAILED",
    )


def _policy_failed(inquiry_id: int, error: Exception) -> HTTPException:
    # Class and inquiry id only: the message could quote inquiry content.
    logger.error(
        "Analysis API: policy evaluation failed for inquiry %s: %s",
        inquiry_id,
        type(error).__name__,
    )
    return ApiHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Policy evaluation failed",
        code="POLICY_FAILED",
    )


def _draft_failed(inquiry_id: int, error: Exception) -> HTTPException:
    # Class and inquiry id only: the message could quote inquiry content.
    logger.error(
        "Analysis API: drafting failed for inquiry %s: %s", inquiry_id, type(error).__name__
    )
    return ApiHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Drafting failed",
        code="DRAFT_FAILED",
    )


def _decision_failed(inquiry_id: int, error: Exception) -> HTTPException:
    # Class and inquiry id only: the message could quote inquiry content.
    logger.error(
        "Analysis API: draft decision failed for inquiry %s: %s", inquiry_id, type(error).__name__
    )
    return ApiHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Decision failed",
        code="DECISION_FAILED",
    )


def _extraction_error(error: ExtractionError) -> HTTPException:
    if isinstance(error, ExtractionNotConfigured):
        return ApiHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured",
            code="ANALYSIS_NOT_CONFIGURED",
        )
    if isinstance(error, ExtractionRateLimited):
        return ApiHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM rate limit reached, try again later",
            code="ANALYSIS_RATE_LIMITED",
        )
    return ApiHTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Analysis failed, try again",
        code="ANALYSIS_FAILED",
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
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None


@router.post(PATH, response_model=AnalysisView)
def analyze(
    inquiry_id: InquiryId,
    engine: Annotated[Engine, Depends(get_engine)],
    extractor: Annotated[InquiryExtractor, Depends(get_extractor)],
    planner: Annotated[Planner, Depends(get_planner)],
    recommender: Annotated[Recommender, Depends(get_recommender)],
    drafter: Annotated[Drafter, Depends(get_drafter)],
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AnalysisView:
    """Analyze the inquiry, replacing its analysis and corrections; on failure nothing changes."""
    try:
        return analyze_inquiry(engine, extractor, inquiry_id, user, planner, recommender, drafter)
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
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
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None


@router.put(PATH, response_model=AnalysisView)
def correct(
    inquiry_id: InquiryId,
    corrections: CorrectionRequest,
    engine: Annotated[Engine, Depends(get_engine)],
    planner: Annotated[Planner, Depends(get_planner)],
    recommender: Annotated[Recommender, Depends(get_recommender)],
    drafter: Annotated[Drafter, Depends(get_drafter)],
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
            planner,
            recommender,
            drafter,
        )
    except AnalysisNotFound:
        raise _no_analysis() from None
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:  # deleted right after the corrections were saved
        raise _inquiry_not_found() from None
    except AnalysisChanged:
        raise ApiHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis changed, reload",
            code="ANALYSIS_CHANGED",
        ) from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None


@router.post(CHECKS_PATH, response_model=AnalysisView)
def recheck(
    inquiry_id: InquiryId,
    engine: Annotated[Engine, Depends(get_engine)],
    planner: Annotated[Planner, Depends(get_planner)],
    recommender: Annotated[Recommender, Depends(get_recommender)],
    drafter: Annotated[Drafter, Depends(get_drafter)],
) -> AnalysisView:
    """Run the checks again for the current analysis (after a stale or failed result)."""
    try:
        return recheck_inquiry(engine, inquiry_id, planner, recommender, drafter)
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except NoAnalysis:
        raise _no_analysis() from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
    except Exception as error:  # a failing check; its run and step are recorded as failed
        raise _checks_failed(inquiry_id, error) from None


@router.post(ORCHESTRATION_PATH, response_model=AnalysisView)
def reorchestrate(
    inquiry_id: InquiryId,
    engine: Annotated[Engine, Depends(get_engine)],
    planner: Annotated[Planner, Depends(get_planner)],
    recommender: Annotated[Recommender, Depends(get_recommender)],
    drafter: Annotated[Drafter, Depends(get_drafter)],
) -> AnalysisView:
    """Run the orchestration again (after a stale, failed or partial result), then the
    recommendation."""
    try:
        return reorchestrate_inquiry(engine, inquiry_id, planner, recommender, drafter)
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except AnalysisNotFound:
        raise _no_analysis() from None
    except NothingToOrchestrate:
        raise ApiHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nothing to orchestrate",
            code="NOTHING_TO_ORCHESTRATE",
        ) from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
    except Exception as error:  # its run and failed step are recorded
        raise _orchestration_failed(inquiry_id, error) from None


@router.post(RECOMMENDATION_PATH, response_model=AnalysisView)
def rerecommend(
    inquiry_id: InquiryId,
    engine: Annotated[Engine, Depends(get_engine)],
    recommender: Annotated[Recommender, Depends(get_recommender)],
    drafter: Annotated[Drafter, Depends(get_drafter)],
) -> AnalysisView:
    """Run only the recommendation again (after a stale or failed result)."""
    try:
        return rerecommend_inquiry(engine, inquiry_id, recommender, drafter)
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except AnalysisNotFound:
        raise _no_analysis() from None
    except NothingToRecommend:
        raise ApiHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nothing to recommend",
            code="NOTHING_TO_RECOMMEND",
        ) from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
    except Exception as error:  # its run and failed step are recorded
        raise _recommendation_failed(inquiry_id, error) from None


@router.post(POLICY_PATH, response_model=AnalysisView)
def reevaluate_policy(
    inquiry_id: InquiryId,
    engine: Annotated[Engine, Depends(get_engine)],
    drafter: Annotated[Drafter, Depends(get_drafter)],
) -> AnalysisView:
    """Evaluate only the policy again (after a stale verdict or a changed threshold)."""
    try:
        return reevaluate_policy_inquiry(engine, inquiry_id, drafter)
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except AnalysisNotFound:
        raise _no_analysis() from None
    except NothingToEvaluate:
        raise ApiHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nothing to evaluate",
            code="NOTHING_TO_EVALUATE",
        ) from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
    except Exception as error:  # its run and failed step are recorded
        raise _policy_failed(inquiry_id, error) from None


@router.post(DRAFT_PATH, response_model=AnalysisView)
def regenerate(
    inquiry_id: InquiryId,
    engine: Annotated[Engine, Depends(get_engine)],
    drafter: Annotated[Drafter, Depends(get_drafter)],
) -> AnalysisView:
    """Draft the current recommendation again: the offer as recommended, status `draft`."""
    try:
        return redraft_inquiry(engine, inquiry_id, drafter)
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except AnalysisNotFound:
        raise _no_analysis() from None
    except NothingToDraft:
        raise ApiHTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Nothing to draft", code="NOTHING_TO_DRAFT"
        ) from None
    except DraftDecided:
        raise ApiHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft already decided",
            code="DRAFT_DECIDED",
        ) from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
    except Exception as error:  # its run and failed step are recorded
        raise _draft_failed(inquiry_id, error) from None


class DraftEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updated_at: AwareDatetime  # of the draft the edit was made on
    option_id: str
    lines: list[LineEdit]
    reason: str | None = None  # required; a missing or blank one is a 422 "Reason is required"


class DraftDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updated_at: AwareDatetime  # of the draft the decision was made on
    action: Literal["approve", "reject"]
    reason: str | None = None  # required to reject, optional to approve


class SupervisorDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updated_at: AwareDatetime  # of the draft the decision was made on
    action: Literal["approve", "reject"]
    reason: str  # required for both; a blank one is a 422 "Reason is required"


def _decision_error(error: Exception) -> HTTPException:
    """The 409/422 of an edit or a decision; `error` is one of the draft service's."""
    if isinstance(error, ReasonRequired):
        return ApiHTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Reason is required",
            code="REASON_REQUIRED",
        )
    if isinstance(error, InvalidEdit):
        # Fixed English sentences of `app.draft.offer` and the service, no inquiry data.
        return ApiHTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            code="INVALID_EDIT",
        )
    details: dict[type[Exception], str] = {
        DraftChanged: "Draft changed, reload",
        DraftNotEditable: "Draft cannot be changed",
        DraftStale: "Draft is stale",
        PolicyMissing: "Policy verdict missing",
        NothingToDraft: "Nothing to draft",
        NotAwaitingSupervisor: "Draft is not awaiting supervisor",
        OwnSubmission: "Cannot approve your own submission",
    }
    codes: dict[type[Exception], str] = {
        DraftChanged: "DRAFT_CHANGED",
        DraftNotEditable: "DRAFT_NOT_EDITABLE",
        DraftStale: "DRAFT_STALE",
        PolicyMissing: "POLICY_MISSING",
        NothingToDraft: "NOTHING_TO_DRAFT",
        NotAwaitingSupervisor: "NOT_AWAITING_SUPERVISOR",
        OwnSubmission: "OWN_SUBMISSION",
    }
    return ApiHTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=details[type(error)],
        code=codes[type(error)],
    )


_DECISION_ERRORS = (
    ReasonRequired,
    InvalidEdit,
    DraftChanged,
    DraftNotEditable,
    DraftStale,
    PolicyMissing,
    NothingToDraft,
    NotAwaitingSupervisor,
    OwnSubmission,
)


@router.put(DRAFT_PATH, response_model=AnalysisView)
def edit(
    inquiry_id: InquiryId,
    request: DraftEditRequest,
    engine: Annotated[Engine, Depends(get_engine)],
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AnalysisView:
    """Edit the draft's offer and evaluate its policy; 409 when the draft changed meanwhile."""
    try:
        return edit_draft_inquiry(
            engine,
            inquiry_id,
            user,
            updated_at=request.updated_at,
            option_id=request.option_id,
            lines=request.lines,
            reason=request.reason,
        )
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except AnalysisNotFound:
        raise _no_analysis() from None
    except _DECISION_ERRORS as error:
        raise _decision_error(error) from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
    except Exception as error:  # an edit's failed policy run is recorded
        raise _decision_failed(inquiry_id, error) from None


@router.post(DECISION_PATH, response_model=AnalysisView)
def decide_draft(
    inquiry_id: InquiryId,
    request: DraftDecisionRequest,
    engine: Annotated[Engine, Depends(get_engine)],
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AnalysisView:
    """Approve or reject the draft; 409 when the draft changed meanwhile."""
    try:
        return decide_draft_inquiry(
            engine,
            inquiry_id,
            user,
            updated_at=request.updated_at,
            action=request.action,
            reason=request.reason,
        )
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except AnalysisNotFound:
        raise _no_analysis() from None
    except _DECISION_ERRORS as error:
        raise _decision_error(error) from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
    except Exception as error:
        raise _decision_failed(inquiry_id, error) from None


@router.post(SUPERVISOR_DECISION_PATH, response_model=AnalysisView)
def supervisor_decide_draft(
    inquiry_id: InquiryId,
    request: SupervisorDecisionRequest,
    engine: Annotated[Engine, Depends(get_engine)],
    user: Annotated[AuthUser, Depends(require_supervisor)],
) -> AnalysisView:
    """Approve or reject a draft awaiting the supervisor (supervisors only, with a reason);
    409 when the draft is not awaiting the supervisor, changed meanwhile, or the approver
    passed it to the supervisor themselves."""
    try:
        return supervisor_decide_inquiry(
            engine,
            inquiry_id,
            user,
            updated_at=request.updated_at,
            action=request.action,
            reason=request.reason,
        )
    except MutationConflict as error:
        raise _mutation_conflict(error) from None
    except InquiryNotFound:
        raise _inquiry_not_found() from None
    except AnalysisNotFound:
        raise _no_analysis() from None
    except _DECISION_ERRORS as error:
        raise _decision_error(error) from None
    except ValidationError:
        raise _invalid_stored_analysis() from None
    except SQLAlchemyError:
        logger.exception("Analysis API: database unavailable")
        raise database_unavailable() from None
    except Exception as error:
        raise _decision_failed(inquiry_id, error) from None
