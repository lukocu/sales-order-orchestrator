<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: S-02 parse-inquiry

- **Plan**: context/changes/parse-inquiry/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-10
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 4 warnings, 5 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | WARNING |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | PASS    |

Success criteria: all 9 automated commands re-run green on f298620 (check.sh 227 passed, alembic check, downgrade/upgrade, frontend lint/typecheck/test/build, docker build). Manual 1.3, 2.4, 3.7, 3.8 verified in-session (Groq call, curl cycle, browser run, Render API run with Groq: parse step `openai/gpt-oss-120b`, priced).

## Findings

### F1 — Migration test drops inquiry_analyses in the dev database

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/tests/test_parsing_models.py:130-139
- **Detail**: `command.downgrade(config, "0003_users_inquiries")` runs against `DATABASE_URL` — the shared compose database used by the dev backend and the `app` container. Every `check.sh` run wipes all stored analyses (observed in-session: an ACME analysis created via curl disappeared after a test run). No earlier migration has such a test.
- **Fix A ⭐ Recommended**: Delete the test; the round-trip is already gate 2.3 (`alembic downgrade 0003 && upgrade head`)
  - Strength: Removes the destructive pattern; coverage is kept by the plan's automated criterion.
  - Tradeoff: Round-trip no longer runs inside pytest/CI.
  - Confidence: HIGH — gate 2.3 already exercises the same downgrade/upgrade.
  - Blind spot: CI may not run gate 2.3 separately.
- **Fix B**: Keep it behind an opt-in pytest marker skipped by default
  - Strength: Preserves the test for deliberate runs.
  - Tradeoff: New marker config; test rarely runs.
  - Confidence: MED — needs pytest config change.
  - Blind spot: None significant.
- **Decision**: FIXED (Fix A — destructive migration test removed; round-trip stays as plan gate 2.3)

### F2 — DB error logs can contain inquiry content; IntegrityError shown as 503

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/db.py:11-18, backend/app/api/analysis.py:101-103, 131-133
- **Detail**: `logger.exception` on `SQLAlchemyError` includes bound parameters (engine lacks `hide_parameters=True`); for the upsert/PUT these are parsed fields (customer, product, phrases), contrary to the "no inquiry content in logs" rule.
- **Fix**: Set `hide_parameters=True` in `build_engine`.
- **Decision**: FIXED (hide_parameters=True in build_engine)

### F3 — No guard against repeated paid LLM calls

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/analysis.py:80-103, backend/app/parsing/service.py:85
- **Detail**: Every POST calls Groq; no per-inquiry or per-user throttle. Demo accounts share one password, so a loop can exhaust the free quota (429 for everyone). The plan explicitly excluded an own rate limit — this is a plan blind spot, not drift.
- **Fix A ⭐ Recommended**: Accept for the demo; record as a follow-up for S-08 (roles) / hardening
  - Strength: Respects the plan's explicit scope; Groq's own 429 is already mapped to 503.
  - Tradeoff: Quota can be drained by anyone with the demo password.
  - Confidence: MED — risk depends on who gets the password.
  - Blind spot: Groq free-tier daily limits not measured.
- **Fix B**: Reject POST with 409 while a `running` trace run exists for the same inquiry, plus a short per-inquiry cooldown
  - Strength: Cheap, blocks concurrent/burst calls.
  - Tradeoff: Scope beyond plan; a loop with pauses still drains quota.
  - Confidence: MED — needs a new query and tests.
  - Blind spot: Stuck `running` runs after a crash would block analysis.
- **Decision**: ACCEPTED (Fix A — demo risk accepted; Groq 429 already maps to 503; follow-up for hardening)

### F4 — Error "Retry" bypasses the re-analysis confirmation

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/components/AnalysisPanel.tsx:539
- **Detail**: After a failed re-analysis the Retry button calls `runAnalysis` directly; with corrections or unsaved edits, success silently replaces them without "Corrections will be lost".
- **Fix**: Use `requestReanalysis` for this Retry button (+ a test).
- **Decision**: FIXED (Retry uses requestReanalysis; test added)

### F5 — Rule-based parser ignores sender_name for the customer

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/parsing/fake.py:169-174
- **Detail**: Plan said customer from the bracketed company in `sender_name`, else the signature; implementation uses only the last body line after a comma (the Protocol has no `sender_name`). A body without a company signature yields e.g. "Pozdrawiam" instead of None. Seed inquiries parse correctly.
- **Fix**: Return None (flagged missing) when the last line has no comma-separated company; note the adaptation in the plan.
- **Decision**: FIXED (closing-phrase last line → customer None; test added; Delta seed still parses)

### F6 — Migration 0004 adds no indexes on new foreign keys

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/migrations/versions/0004_inquiry_analyses.py:21-45, backend/app/parsing/models.py:31
- **Detail**: 0002/0003 index their FKs (`ix_trace_steps_run_id`, user_sessions.user_id); 0004's `run_id`, `analyzed_by`, `corrected_by` (ON DELETE SET NULL) have none. Harmless at current size.
- **Fix**: New migration 0005 adding `ix_inquiry_analyses_run_id` (0004 is already deployed; don't edit it).
- **Decision**: FIXED (migration 0005_inquiry_analyses_run_index + index=True in model)

### F7 — Stored JSON that fails validation becomes a bare 500

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/parsing/service.py:203-204
- **Detail**: `ParsedFields` is `extra="forbid"`; a future schema change makes old JSONB rows raise `ValidationError`, which handlers don't catch.
- **Fix**: Note it as a rule: any `ParsedFields` change needs a data migration (no code change now).
- **Decision**: FIXED + ACCEPTED-AS-RULE: Zmiana schematu pól zapisanych w JSONB wymaga migracji danych (ValidationError → 500 "Stored analysis is invalid", class-only log; test added)

### F8 — 409 discards edits immediately; notice wording misleads

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/components/AnalysisPanel.tsx:352-354
- **Detail**: On 409 the panel reloads at once, dropping unsaved edits, while showing "Analysis changed, reload" as if the reload were pending.
- **Fix**: Change notice to "Analysis changed by a re-analysis — reloaded, your unsaved edits were discarded."
- **Decision**: FIXED (notice: "Analysis changed by a re-analysis — reloaded, your unsaved edits were discarded.")

### F9 — LLM timeout is per-operation and undocumented

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/parsing/openai_compatible.py:108-114, .env.example
- **Detail**: `httpx.Client(timeout=30)` applies per connect/read/write, so a trickling response can exceed 30 s total; `LLM_TIMEOUT_SECONDS` is not listed in `.env.example`.
- **Fix**: Add `LLM_TIMEOUT_SECONDS` to `.env.example` comment; accept per-operation timeout for the MVP.
- **Decision**: FIXED (LLM_TIMEOUT_SECONDS documented in .env.example; per-operation timeout accepted)
