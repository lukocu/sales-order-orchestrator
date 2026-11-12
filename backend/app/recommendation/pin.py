"""Whether a stored recommendation was computed from the current data.

A recommendation is pinned to the analysis version, the check result (`checked_at`) and the
orchestration (`orchestrated_at`) it was computed from. Kept apart from
`app.recommendation.service` so the policy stage, which that service calls, can share the
same definition without an import cycle.
"""

from datetime import datetime

from sqlmodel import Session, col, select

from app.checks.service import analysis_version, current_checks
from app.orchestration.models import InquiryOrchestration
from app.parsing.models import InquiryAnalysis
from app.recommendation.models import InquiryRecommendation


def pinned_to(
    row: InquiryRecommendation,
    version: datetime,
    checks_checked_at: datetime | None,
    orchestrated_at: datetime | None,
) -> bool:
    """True when the row was computed from exactly these current values."""
    return (
        row.analysis_version == version
        and row.checks_checked_at == checks_checked_at
        and row.orchestrated_at == orchestrated_at
    )


def is_current(session: Session, row: InquiryRecommendation, analysis: InquiryAnalysis) -> bool:
    """True when the row is pinned to the analysis' current check result and orchestration."""
    version = analysis_version(analysis)
    checks = current_checks(session, analysis.inquiry_id, version)
    orchestrated_at = session.exec(
        select(InquiryOrchestration.orchestrated_at).where(
            col(InquiryOrchestration.inquiry_id) == analysis.inquiry_id
        )
    ).first()
    return pinned_to(row, version, None if checks is None else checks.checked_at, orchestrated_at)
