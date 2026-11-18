# API error codes

Error responses preserve the existing HTTP status and `detail`, adding a stable
`code`. Clients identify errors by code, translate at render time, and keep raw
`detail` for diagnostics. No endpoint currently emits translation `params`;
exception text, request bodies, credentials and mailbox messages must never be
copied into parameters. Unknown codes must use a safe localized generic message.

| Area | Codes |
| --- | --- |
| Session and access | `NOT_AUTHENTICATED`, `INVALID_CREDENTIALS`, `SUPERVISOR_REQUIRED`, `LOGIN_BUSY` |
| Resources | `INQUIRY_NOT_FOUND`, `RUN_NOT_FOUND`, `NO_ANALYSIS`, `NOT_FOUND` |
| Input | `VALIDATION_ERROR`, `REASON_REQUIRED`, `INVALID_EDIT` |
| Concurrent changes | `ANALYSIS_CHANGED`, `INQUIRY_CHANGED`, `DRAFT_CHANGED`, `AWAITING_SUPERVISOR` |
| Decisions | `DRAFT_DECIDED`, `DRAFT_NOT_EDITABLE`, `DRAFT_STALE`, `POLICY_MISSING`, `NOT_AWAITING_SUPERVISOR`, `OWN_SUBMISSION` |
| Prerequisites | `NOTHING_TO_ORCHESTRATE`, `NOTHING_TO_RECOMMEND`, `NOTHING_TO_EVALUATE`, `NOTHING_TO_DRAFT` |
| Processing | `STORED_ANALYSIS_INVALID`, `CHECKS_FAILED`, `ORCHESTRATION_FAILED`, `RECOMMENDATION_FAILED`, `POLICY_FAILED`, `DRAFT_FAILED`, `DECISION_FAILED` |
| Analysis provider | `ANALYSIS_NOT_CONFIGURED`, `ANALYSIS_RATE_LIMITED`, `ANALYSIS_FAILED` |
| Mailbox | `MAILBOX_NOT_CONFIGURED`, `MAILBOX_AUTH_FAILED`, `MAILBOX_UNAVAILABLE`, `MAILBOX_ERROR`, `MAILBOX_BUSY` |
| Infrastructure | `DATABASE_UNAVAILABLE`, `INTERNAL_ERROR` |
| Framework fallbacks | `FORBIDDEN`, `METHOD_NOT_ALLOWED`, `RATE_LIMITED`, `HTTP_ERROR` |

Codes are assigned by the endpoint or exception type, never by matching an
exception's message. `VALIDATION_ERROR` keeps FastAPI's legacy `detail` array.
Unanticipated errors return generic `INTERNAL_ERROR` with the original exception
and traceback logged. Existing stage-specific sanitized logging is unchanged.
HTTP headers are preserved; failed logout still clears the session cookie.

A degraded health response retains `status`, `database` and `migration`, and adds
`detail` and `code: DATABASE_UNAVAILABLE`. Successful health payloads are unchanged.

Contract coverage: `tests/test_api_errors.py`, existing auth/API integration tests,
and decision/mutation integration tests. Authentication distinguishes invalid
credentials from a missing/expired session. Decision codes distinguish a changed
version, pending review, stale data and approving one's own submission.
