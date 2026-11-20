<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Shareable URLs (S-17)

- **Plan**: context/changes/shareable-urls/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2
- **Date**: 2026-11-20
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 1 observations (all fixed after triage)

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | PASS    |
| Safety & Quality    | PASS    |
| Architecture        | PASS    |
| Pattern Consistency | PASS    |
| Success Criteria    | PASS    |

Automated gates re-run during the review: `npm run lint`, `npm run typecheck`, `npm test` (29 files, 625 tests) and `npm run build` all pass. Manual rows 1.5, 1.6, 2.4 and 2.5 are ticked with a SHA and were run in the browser (no screenshots). `InboxRoute.tsx` is listed in the plan but needed no change. Extras: the pathname guard in the canonicalising effect and the `path` prop of `Routed` in the kitchen sink; both support the planned behaviour.

## Findings

### F1 — Approval inspector routes have no test

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: frontend/src/components/SupervisorQueue.test.tsx
- **Detail**: The Phase 2 contract says approval inspector routes keep the queue context and the role restriction. `/approvals/$inquiryId/run` is unchanged and no test opens it: a salesperson being denied there and a supervisor getting the inspector, with Close returning to `/approvals/17`.
- **Fix**: Add two tests to SupervisorQueue.test.tsx for `/approvals/17/run` (salesperson denied without a review request; supervisor sees the inspector and Close goes to `/approvals/17`).
- **Decision**: FIXED

### F2 — Canonicalising guard breaks on a trailing slash

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/components/AnalysisPanel.tsx:406
- **Detail**: The effect returns early unless `history.location.pathname` equals `/inquiries/<id>` (or `/run`) exactly. With `/inquiries/5/` or a future basepath it returns forever, so the step is never added to the URL and nothing reports it.
- **Fix**: Compare against the matched route's own pathname (`inquiryMatch.pathname` / `inspecting.pathname`) instead of a rebuilt string.
- **Decision**: FIXED

### F3 — Fallback message wording for invalid links

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/i18n/locales/en.json (steps.unavailableLink)
- **Detail**: "This step is no longer available" is also shown for a nonsense value such as `?step=foo`, where nothing "no longer" applies. A numeric `?step=5` is dropped by `validateSearch` and gets no message at all.
- **Fix**: Neutral wording in both locales, e.g. "This link's step can't be opened. Showing {{step}} instead."
- **Decision**: FIXED
