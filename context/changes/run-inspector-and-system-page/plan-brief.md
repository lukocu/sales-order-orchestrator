# Run inspector and system page (S-11) — Plan Brief

> Full plan: `context/changes/run-inspector-and-system-page/plan.md`
> Research: `context/changes/run-inspector-and-system-page/research.md`

## What & Why

The inquiry view reads like a technical report. Six metric blocks, agent and planner names, raw variant ids and step costs sit between the salesperson and the decision (UX audit: ~10 000 px page, 20+ metric cards). PRD FR-015 splits the UI into a business layer and an on-demand technical layer. This change builds the technical layer's two homes: a **run inspector** and a **system page**. It also brings in the routing they need and empties the business flow of diagnostics.

## Starting Point

There is no router: the session picks the view and the selected inquiry lives in component state. Every run (parsing, checks, orchestration, recommendation, policy, draft) and the orchestrator plan already arrive in one `GET /api/inquiries/{id}/analysis` response. They are rendered inline via `RunMetrics` in six sections. The system status is a `HealthFooter` in the shell. The F-03 compatibility CSS block still styles the inquiry view's raw buttons.

## Desired End State

The inbox, an inquiry, its run inspector and the system page each have a URL (`/`, `/inquiries/42`, `/inquiries/42/run`, `/system`) that survives a reload. Signed out, each URL renders sign-in in place and is still there afterwards. "How was this calculated?" opens a Sheet with the plan by stage, every run's steps (tokens, cost, time) and totals. The inquiry page itself shows only business data. The legacy compatibility block and `HealthFooter` are gone.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Router | TanStack Router, code-based routes, `createAppRouter(history?)` | Already chosen in `tech-stack.md`; no generator keeps TS 7 / Vite 8 risk low | Research |
| Inspector shape | shadcn Sheet at `/inquiries/$id/run` over the inquiry | Meets US-03 ("without leaving the inquiry") and FR-020 (own URL) together | Plan |
| Inquiry URL | `/inquiries/$id` now; explicit `?redirect=` and steps stay S-17 | The inspector needs a parent in the URL; sign-in renders in place, so the URL is kept | Plan |
| Inspector data | Rendered inside `AnalysisPanel` from its loaded `Analysis`; latest run per section | No refetch, always matches the page; no backend work | Plan |
| Identifiers outside metrics | Remove now (ids, enum, agent/planner/recommender names, jargon); readable variant names in S-13 | S-11's outcome says identifiers disappear | Plan |
| Edit form option select | Interim label `{kind} · {value}` | Needs some label without ids until S-13 | Plan |
| Compat block | Delete it entirely after converting ~25 buttons to `Button` | Closes the F-03 deferral; S-12 starts clean | Plan |
| System page content | API, database, migration from public `/api/health`, with Refresh | Exactly US-03; backend unchanged | Plan |
| Tests | Vitest on memory history + kitchen sink + manual check; no E2E | F-03 pattern, CI unchanged | Plan |
| F-03 follow-ups | None marked S-11 (F6 → S-14; F5 already fixed) | Checked `review-fixes.md` and the impl review | Research |

## Scope

**In scope:**
- router, nav, not-found;
- inquiry URL;
- system page;
- run inspector;
- removing diagnostics and identifiers from six sections;
- buttons to `Button`;
- deleting `HealthFooter`, `RunMetrics`, `.status*`, `.metrics__step*` and the compat block;
- AGENTS.md and tech-stack.md updates.

**Out of scope:**
- run history and any backend change;
- `?redirect=` and steps in the URL (S-17);
- the supervisor queue (S-15);
- readable variant names (S-13);
- translating untouched section text and the step layout (S-12);
- backend message translation (S-16);
- sign-out focus (S-14);
- E2E.

## Architecture / Approach

`main.tsx` renders `RouterProvider(createAppRouter())`. The root route component is `App`, which keeps the session state machine. It renders `AppShell` with `AppNav`, plus either sign-in or `<Outlet />`. Child routes: `/` and `/inquiries/$inquiryId` render `Inbox` (selection from the param); `/inquiries/$inquiryId/run` is matched by `AnalysisPanel` to open `RunInspector`; `/system` renders `SystemPage`; everything else renders `NotFound`. `onUnauthorized` reaches views via a small session context.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Router and inquiry address | URLs for inbox/inquiry, nav, not-found, in-place sign-in | Session effect remounting under the router; kitchen sink and App tests need router wrapping |
| 2. System page | `/system` on tokens; footer and `.status*` gone | Small |
| 3. Run inspector | Sheet with plan, steps, totals at `/run` | Focus return on a cold-opened URL; shadcn add output needs cleanup |
| 4. Clean business layer | No diagnostics or ids in six sections | ~45 test assertions to move; wording of replaced texts |
| 5. Remove compat block | Buttons on `Button`, block deleted, docs | Visual regressions in sections S-12 has not rebuilt yet |

**Prerequisites:** F-03 merged (done, PR #4); `npm` access to add `@tanstack/react-router` and the shadcn `sheet` and `table`.
**Estimated effort:** ~3–4 sessions across 5 phases (Phase 4 is the largest).

## Open Risks & Assumptions

- The inspector shows only the latest run per section. A re-run hides the earlier run's cost, which is acceptable for S-11 and noted as out of scope.
- The capability-slug → readable label map in OrchestrationSection must cover the slugs the backend actually sends. The fallback label keeps unknown slugs readable but generic.
- Converting buttons before S-12 may set variants that S-12 changes again. That is accepted, because the compat block cannot go otherwise.

## Success Criteria (Summary)

- A salesperson works an inquiry without seeing tokens, costs, agents, planners or raw ids. An operator finds all of it one click away, at a URL that can be reloaded.
- Signed-in users see system status on `/system`; signed-out visitors see nothing technical.
- `HealthFooter`, `RunMetrics` and the compatibility CSS are deleted; lint, typecheck, tests and build are green.
