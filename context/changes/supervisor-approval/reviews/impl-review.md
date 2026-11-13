<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Supervisor approval (S-08)

- **Plan**: context/changes/supervisor-approval/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-13
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 4 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | WARNING |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | PASS    |
| Success Criteria    | PASS    |

Success criteria were rechecked during this review:

- Backend `check.sh`: 811 passed.
- `alembic check`: "No new upgrade operations detected".
- Frontend: 221 tests passed; typecheck, lint and build all pass.

The manual items (1.4, 2.3, 3.6–3.8) are marked done. Each was confirmed during implementation, and 3.8 was also confirmed on Render.

## Findings

### F1 — The submitter (four-eyes check) is chosen by the application clock time

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/draft/service.py:934
- **Detail**:
  - `_submitted_by` sorts decisions by `decided_at DESC, id DESC`, and `decided_at` comes from `datetime.now(UTC)` in the application process.
  - Decisions on one draft are serialized by the analysis lock, so `id` order is the true commit order.
  - With several workers and clock skew, a decision by another user could get a later `decided_at` than the submitter's approve. The submitter would then not be recognised and could approve their own submission.
  - Today Render runs a single process, so the risk is theoretical. History ordering (`service.py:466`) uses the same pattern.
- **Fix**: Sort `_submitted_by` by `id DESC` only (history can stay as it is).
- **Decision**: FIXED

### F2 — The `ix_inquiry_drafts_status` index is unused by any query

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/migrations/versions/0013_supervisor_decisions.py:26, backend/app/draft/models.py:37
- **Detail**:
  - The plan added the index "to speed up the inbox filter".
  - The "Awaiting supervisor only" filter actually runs in the browser (`frontend/src/components/Inbox.tsx:136-140`), and `list_inquiries` never filters by status.
  - The index is cheap but dead for now. This is an error in the plan, not drift.
- **Fix**: Leave it as preparation for a server-side filter, and note in the plan that it is unused for now. Removing it would need a migration 0014, which is not worth it.
- **Decision**: FIXED

### F3 — A stale draft in `awaiting_supervisor` is counted in the filter but cannot be acted on

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/components/Inbox.tsx:136-140, frontend/src/components/ReplyDraftSection.tsx:170,247
- **Detail**:
  - `draft_status` is the raw status, so a stale awaiting draft gets the badge and is counted in "Awaiting supervisor only (N)".
  - In the panel, `supervisorActions` and the salesperson note "Waiting for a supervisor decision." require `!draft.stale`, and Regenerate is blocked for `awaiting_supervisor`.
  - Both roles therefore see only the generic stale note, until a new recommendation replaces the draft.
  - The plan accepts this case explicitly (plan.md:252-254). The cause is the UX: there is no hint about what to do next.
- **Fix**: Add a line for a stale awaiting draft, such as "The recommendation changed — re-run it to continue."
- **Decision**: FIXED

### F4 — `ChecksSection.tsx` changed outside the plan, and `App.tsx` was not changed

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/src/components/ChecksSection.tsx:25,61-67,399-412
- **Detail**:
  - `ReplyDraftSection` is rendered inside `ChecksSection`, so `user` and `onSupervisorDecideDraft` have to pass through it. The plan's file list left this out.
  - `App.tsx` needed no change, because `Inbox` already received `user`.
  - There is also a harmless addition: the empty state "No inquiries awaiting a supervisor." (`Inbox.tsx:184-186`).
- **Fix**: Note this in the plan as an addendum (no code change).
- **Decision**: FIXED
