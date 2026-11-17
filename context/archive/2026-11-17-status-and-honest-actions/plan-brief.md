# Visible status and honest action labels — Plan Brief

> Full plan: `context/changes/status-and-honest-actions/plan.md`

## What & Why

Roadmap S-14 (FR-018, US-02, FR-011, WCAG 4.1.3). The user always sees one status of an inquiry, on the list, in the header and as an announced message after every decision. The salesperson's action says what will happen: "Wyślij do przełożonego" when the policy requires approval. The UX audit rated the misleading "Approve" and the missing feedback as severity 4.

## Starting Point

The list shows two loose badges (outcome, awaiting supervisor), the header shows no status, "Zatwierdź" is used whatever the verdict, and only a rejection is announced. The backend already routes a `requires_supervisor` approval to `awaiting_supervisor`. Sign out drops focus to `<body>` (F6, deferred from F-03).

## Desired End State

Each inbox row and the open inquiry's header show one status: Nowe, Przeanalizowane, Wyjątek, Wymaga uzupełnienia, Czeka na przełożonego, Gotowe do wysłania, Odrzucone. It updates immediately after any change. With `requires_supervisor` the action reads "Wyślij do przełożonego" with a hint. After every decision the status line at the top of the panel says what happened. Sign out keeps focus, says "Wylogowywanie…", then focuses the sign-in heading.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Where the status is derived | Frontend function from `analyzed` + `outcome` + `draft_status`; backend adds only `analyzed` | One rule for list and header, and in-place updates after decisions keep working without a refetch. |
| Status priority | Draft status (awaiting / ready / rejected) > outcome (exception / needs input) > analysed > new | A draft exists only for an exception, so its status is the more specific fact. |
| `needs_input` | Seventh status "Wymaga uzupełnienia" | Hiding it as "analysed" would conceal that the salesperson has work to do. |
| Message after a decision | Existing `role="status"` line, kept mounted; no sonner | No new dependency, already tested, and the message stays visible. |
| Rejections | Keep S-12's step-back message, add nothing | Avoids a double announcement. |
| Label source | `draft.policy` (the verdict in force) | It is the same verdict the backend's `decide()` uses, also for an edited offer. |
| F6 sign-out focus | Included as phase 3 | The F-03 review assigned it to S-14. |
| Stale draft / history | Raw `draft_status`, current status only | Same as today's awaiting filter; history is out of scope. |

## Scope

**In scope:** `analyzed` on list/detail API; `inquiryStatus` + 7 PL/EN labels; one status badge on rows and in the header; merged `onStatusFacts` callback; "Send to supervisor" label, form, submit and hint; notices after approve / send to supervisor / edit / supervisor approval; always-mounted status region; sign-out `aria-disabled`, "Signing out…" and focus on the sign-in heading; kitchen-sink states.

**Out of scope:** API status field; status history after regenerate; staleness on the list; toasts; supervisor buttons, filter and permissions (S-15); live list refresh; migrations.

## Architecture / Approach

Backend: `InquirySummary.analyzed` from the `inquiry_analyses` join that already exists. Frontend: pure `inquiryStatus(facts)` + `STATUS_VARIANT`; `Inbox` renders the badge on rows and the header and updates facts in place from `AnalysisPanel.onStatusFacts`. `ReplyDraftSection` picks labels from `draft.policy.outcome`; `AnalysisPanel.decideOnReplyDraft` sets a notice from the action and resulting status unless `stepBackReason` already announces it. `App`/`AppShell`/`LoginForm` handle sign-out focus.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Status on the list and in the header | `analyzed` field, status rule, one badge on rows and header, merged callback | Many fixtures and tests build `InquirySummary` and assert the old badges |
| 2. Honest label and messages | "Send to supervisor" label/form/hint, notice after every decision | Live region announcement depends on the container staying mounted |
| 3. Sign-out focus (F6) | Focus kept while signing out, then on the sign-in heading | Must not steal focus on the first load |

**Prerequisites:** S-12 (done). Backend tests need PostgreSQL running.
**Estimated effort:** ~2 sessions across 3 phases.

## Open Risks & Assumptions

- `outcome.*` and `inbox.badgeAwaiting` may be used elsewhere; they are removed only if a grep finds no users.
- Removing the separate outcome badge assumes the status badge carries all the information the list needs (exception / needs input are statuses).

## Success Criteria (Summary)

- Every inbox row and the open inquiry show the same single status, and it changes right after any decision.
- A salesperson never sees "Approve" for an offer that will go to the supervisor, and every decision is confirmed by an announced message.
- Signing out by keyboard never loses focus.
