---
date: 2026-11-16T16:00:00+01:00
researcher: Claude (10x-research, side session of M-2 kickoff)
git_commit: afd99f0
branch: claude/compassionate-neumann-f9bf84
repository: agent-orchestrator
topic: "S-11 run-inspector-and-system-page: what exists today for routing, run diagnostics, system status and the legacy inquiry CSS"
tags: [research, frontend, routing, run-inspector, system-page, health, legacy-css, i18n]
status: complete
last_updated: 2026-11-16
last_updated_by: Claude
---

# Research: S-11 Run inspector and system page

**Date**: 2026-11-16
**Git Commit**: afd99f0 (branch `claude/compassionate-neumann-f9bf84`, on top of `main` f2998ca)
**Repository**: agent-orchestrator

## Research Question

Roadmap S-11 (`context/foundation/roadmap.md:95-105`): the user opens a "Run inspector" from the inquiry view and sees the orchestrator plan, agent results, and tokens/cost/time per step and in total; system status is on a separate page available after sign-in; metrics, agent names, the migration number and other technical identifiers disappear from the salesperson's flow and from the sign-in screen. PRD refs FR-015, FR-005, US-03, FR-020, NFR (operator sees tokens, cost, time), Access Control.

The brief adds four things the plan must cover: introduce routing; move `HealthFooter` out of the shell onto the system page; remove the `.inbox__detail` compatibility block in `legacy.css` for the views S-11 rebuilds; pick up the F-03 follow-ups marked S-11.

This document answers: what is in place for each of those, what data the inspector and system page can use without backend work, where the technical content sits in the inquiry view today, and which choices remain for `/10x-plan`.

## Summary

1. **There is no router.** `App.tsx:26` picks the view from the session alone, and `Inbox.tsx:78` keeps the selected inquiry in `useState`; nothing in `frontend/src` reads or writes the URL. `context/foundation/tech-stack.md` ("Frontend → Parked") already names **TanStack Router** as the router (parked for S-17). `@tanstack/react-router` 1.170.46 declares peer `react >=18 || >=19` (npm registry, checked 2026-11-16). Code-based routing (`createRootRoute`/`createRoute`) works without the Vite file-route plugin.
2. **Deep links already work on the server.** The FastAPI catch-all `backend/app/main.py:31-40` returns `index.html` for any non-`/api` path that is not a static file (covered by `backend/tests/test_spa.py:21-27`). The Vite dev server falls back to HTML by default (no `appType` override in `frontend/vite.config.ts`). No backend change is needed for client routes, as long as no route starts with `/api`.
3. **All run data the inspector needs is already in one response.** `GET /api/inquiries/{id}/analysis` returns `Analysis`, which holds six `run: RunSummary | null` fields: `Analysis.run`, `ChecksView.run`, `OrchestrationView.run`, `RecommendationView.run`, `PolicyView.run`, `ReplyDraftView.run` (`frontend/src/api/analysis.ts:487,150,267,339,367,441`). The orchestration plan (stages, `depends_on`, agent, reason, per-task result) is in `OrchestrationView` (`analysis.ts:239-267`). Backend `GET /api/runs/{run_id}` exists (`backend/app/api/runs.py:18-33`, protected) but has no frontend client, and there is no "runs for an inquiry" endpoint. The inspector can be built frontend-only.
4. **System status has one source: the public `/api/health`** (`backend/app/api/health.py`; `{status, database, migration}`; on `api_router`, not `protected_router`, `main.py:20`). The PRD keeps it public for the platform (`prd.md` Access Control) and only forbids showing it in the UI before sign-in. `HealthFooter` is rendered only when authenticated (`App.tsx:102`), so the sign-in screen no longer shows the migration today (an F-03 decision). S-11 moves the component to a route.
5. **Technical content in the inquiry view is wider than the six `RunMetrics` blocks.** The inventory below has 27 rows across 6 files: 25 technical or identifier-leaking sites, plus 2 business rows in OrchestrationSection kept for contrast. They fall into two groups. The first moves to the inspector: RunMetrics ×6, ChecksSection inline totals, orchestration plan stages, `capability → agent`, attempts, durations, `error_type`, planner and recommender names, wall time. The second stays in the business layer but leaks identifiers: the raw variant id in Recommendation, Policy, Draft, the Edit select and the decision history; the uppercase confidence enum; "completed without agents"; "Rule-based demo parser (no LLM)".
6. **The `.inbox__detail` compatibility block (`legacy.css:678-775`) mostly serves raw `<button>`s.** It restores browser defaults for headings, lists, `dl`/`dd`, `pre`, button, checkbox and textarea. Its main remaining job is the old button look for about 25 classless `<button>` elements across all six inquiry sections (none uses the shadcn `Button`). Deleting the whole block in S-11 means converting every inquiry-view button, which overlaps S-12's rebuild. What S-11 can delete outright is CSS that becomes dead: `.status*` (`legacy.css:53-107`, HealthFooter only) and `.metrics__steps/__step/__step--total/__name` (`:259-282`, RunMetrics only).
7. **No open F-03 follow-up is marked S-11.** `context/archive/2026-11-16-design-system-i18n-foundation/follow-ups/review-fixes.md` holds one item, F6 (focus drops on sign-out), owned by S-14. The impl-review's F5 (date locale in `format.ts`, which mentioned S-11/S-12) was **FIXED** in F-03 (`reviews/impl-review.md`, F5 "Decision: FIXED"). The S-11 items inherited from F-03 are the two plan deferrals: move HealthFooter (`plan.md:40`) and delete the compat block (`plan.md:121`, `:517`).

## Detailed Findings

### Routing and app structure

- `frontend/src/main.tsx` renders `<App />` in `StrictMode`; i18n is imported there.
- `App.tsx:11-16`: a `State` union (`loading | anonymous | authenticated | error`) from `fetchMe` (`App.tsx:27-41`). Anonymous renders `LoginForm` (`:93`), authenticated renders `Inbox` + `HealthFooter` (`:99-102`). 401s from children call `handleSignedOut` via `onUnauthorized` (`:47-51`, passed at `:100`).
- `AppShell.tsx:13` already reserves a `nav?: ReactNode` slot "for later views (S-11, S-15)". It renders the slot between the title and the language switch (`:30`); the content width is `max-w-lg` for anonymous and `max-w-5xl` when signed in (`:21`).
- `Inbox.tsx:78`: `selectedId` is component state; the detail is fetched in an effect (`:97-109`); `AnalysisPanel` is keyed by inquiry id (`:319-326`). A reload loses the selection.
- Since the login form renders in place (no redirect), keeping the URL while signed out and rendering the routed view after sign-in would already return the user to the same address. Doing it explicitly (`beforeLoad` + `redirect` with a `redirect` search param, per the TanStack "authenticated routes" guide) is the S-17 outcome (`roadmap.md:169-178`). The S-17 risk note says routes for the system page come in S-11.
- Tests: Vitest + jsdom (`vite.config.ts` test block, `src/test/setup.ts` pins English). The TanStack docs give `createMemoryHistory({ initialEntries })` + `createRouter({ routeTree, history })` for non-browser rendering. Adding a dependency changes `package-lock.json`, used by `npm ci` in CI (`.github/workflows/ci.yml`, job `frontend`) and in the `Dockerfile`.

### Serving client routes

- `backend/app/main.py:25-40` `_add_spa_routes`: `/api` and `/api/*` → JSON 404 (`:35-36`); existing static file → file (`:37-39`); anything else → `index.html` (`:40`). It is mounted only if `static_dir/index.html` exists (`:46-47`).
- `frontend/index.html` loads `/src/main.tsx` with an absolute path, and Vite's default `base: '/'` gives absolute asset URLs, so nested paths such as `/inquiries/12/run` load assets correctly.
- `render.yaml` has no rewrites; `healthCheckPath: /api/health`.

### Run data available to the inspector

- Backend trace model: `TraceRun` / `TraceStep` (`backend/app/tracing/models.py:18-65`); summary builder `get_run_summary` (`backend/app/tracing/summary.py:153`, steps ordered by `started_at`, `id`). `raw_usage` is never exposed.
- Frontend types (`frontend/src/api/analysis.ts`):
  - `StepSummary` (`:40-57`): name, `kind: 'deterministic' | 'llm'`, status, error_type, provider, model, input/output/cache tokens, cost_usd, price_status, price_source, started_at, duration_ms.
  - `RunTotals` (`:59-67`) and `RunSummary` (`:69-76`), validated by `isRunSummary` (`:683`).
- Each section row keeps only its **current** `run_id` (FK `ondelete SET NULL`, e.g. `backend/app/orchestration/models.py:104`). Older runs for the same inquiry stay in `trace_runs` (subject `inquiry`, `subject_id = str(inquiry_id)`, indexed) but nothing reads them. An inspector built on `Analysis` shows the latest run per section, not history.
- Orchestration plan (`backend/app/orchestration/schema.py:143-175`; frontend `analysis.ts:239-267`):
  - `OrchestrationResult` fields: `consent`, `planner`, `planner_choice {tasks[{capability, reason}], summary}`, `planner_steps`, `tasks[TaskOutcome]`, `error`.
  - `TaskOutcome` fields: `capability`, `agent`, `reason`, `depends_on`, `stage` (1-based), `status`, `steps` (trace step names), `error_type`, `result`.
  - Parallelism is implicit: tasks with the same `stage` ran in parallel (`backend/app/orchestration/executor.py:103-126`). The UI already groups by stage (`OrchestrationSection.tsx:128-139`).
  - To join a task to its trace steps, match `TaskOutcome.steps` / `planner_steps` against `StepSummary.name`. `taskDuration` already does this (`OrchestrationSection.tsx:121-126`).
- One orchestration row per inquiry (unique `inquiry_id`), so a re-run replaces the plan; there is no plan history.
- `RecommendationView.choice_steps` (`analysis.ts:334`) and `planner_steps` (`:262`) are typed but not rendered anywhere.

### System status

- `backend/app/api/health.py`: `HealthResponse {status: 'ok' | 'degraded', database: 'ok' | 'error', migration: str | None}`. It runs `SELECT 1` plus the alembic current revision; on `SQLAlchemyError` it returns 503 with `degraded`/`error`/`None`. It is public.
- `frontend/src/api/health.ts` uses raw `fetch` rather than `client.ts`, so a 401 would not map to `UnauthorizedError`; that is irrelevant for a public endpoint. It returns `{kind: 'ok' | 'degraded', health}` or `{kind: 'error', message}`.
- `HealthFooter.tsx:19-35`: a `<footer class="status status--{kind}" aria-live="polite">` with an `<h2>`, summary and `dl` (API, database, migration). Its strings already go through `t('health.*')`. Its styling is legacy `.status*` only.
- Searched `backend/app/api/` (health, auth, runs, inquiries, analysis, mailbox): there is no other status endpoint. It has no version, uptime, LLM provider or mailbox config. A richer system page would need a new protected endpoint; the S-11 outcome only names API, database and migration (US-03, `prd.md:81`).
- Kitchen sink: `HealthFooter` appears only through `<App />` in the authenticated "Sign out failed" cell (`kitchen-sink.tsx:368-379`), fed by the default `GET /api/health` stub (`:58-65`).

### Technical content in the inquiry view (inventory)

| file:line | renders | source | where it belongs |
|---|---|---|---|
| AnalysisPanel.tsx:457-458 | "Rule-based demo parser (no LLM)" banner when `extractor === 'fake'` | `Analysis.extractor` | technical (inspector) |
| AnalysisPanel.tsx:211-214 | "edited · model: X" on corrected fields | `model_fields`, `corrected_fields` | business (the original value) but worded technically |
| AnalysisPanel.tsx:591 | `<RunMetrics run={analysis.run} />` ("Metrics") | `Analysis.run` | inspector |
| ChecksSection.tsx:119 | "Standard inquiry — completed without agents" | `ChecksView.outcome` | business wording leaks "agents" |
| ChecksSection.tsx:120-133 | inline Tokens / Cost / Duration / Steps totals in the standard banner | `ChecksView.run` | inspector |
| ChecksSection.tsx:429 | `<RunMetrics label="Checks metrics">` | `ChecksView.run` | inspector |
| OrchestrationSection.tsx:148 | `{capability} → {agent}` | `TaskOutcome` | inspector |
| OrchestrationSection.tsx:153-158 | Reason, Attempts, Duration | `TaskOutcome`, run steps | inspector |
| OrchestrationSection.tsx:171-175 | `error_type` (exception class) | `TaskOutcome.error_type` | inspector |
| OrchestrationSection.tsx:291-296 | "Planner: {summary}", "· planner {name}" | `planner_choice.summary`, `planner` | inspector |
| OrchestrationSection.tsx:192-212 | ErrorBox codes, "Rejected planner choice" | `OrchestrationView.error` | inspector (a short business message may remain) |
| OrchestrationSection.tsx:128-140, 303-315 | stage titles "Stage N — in parallel, after: slug" | `stage`, `depends_on` | inspector (FR-005) |
| OrchestrationSection.tsx:317-318 | `<RunMetrics label="Orchestration metrics">`, "Wall time · sum of steps" | `OrchestrationView.run` | inspector |
| OrchestrationSection.tsx:94-118, 159-170 | agent findings (substitutes, supplier offers, history) | `TaskOutcome.result` | **business**: feed the decision |
| OrchestrationSection.tsx:284-290 | status banner, substitute consent | `status`, `consent` | business |
| RecommendationSection.tsx:279-280 | "· recommender {name}" | `recommender` | inspector |
| RecommendationSection.tsx:140-141 | `HIGH/MEDIUM/LOW confidence` (raw enum) | `RecommendationOption.band` | business, needs a readable label |
| RecommendationSection.tsx:145-146 | "Option" → raw variant id | `RecommendationOption.id` | identifier leak (FR-015) |
| RecommendationSection.tsx:181-190 | "Recommender failed / Choice rejected: {code}" | `RecommendationView.error` | inspector (code) |
| RecommendationSection.tsx:314 | `<RunMetrics label="Recommendation metrics">` | `.run` | inspector |
| PolicySection.tsx:163 | "· option {option_id}" | `PolicyView.option_id` | identifier leak |
| PolicySection.tsx:199 | `<RunMetrics label="Policy metrics">` | `.run` | inspector |
| ReplyDraftSection.tsx:304 | "· option {option_id}" | `offer.option_id` | identifier leak |
| ReplyDraftSection.tsx:307-310 | "model's paragraphs were unavailable; fallback text" | `text_source` | borderline (business-relevant warning, technical wording) |
| ReplyDraftSection.tsx:351 | `<RunMetrics label="Draft metrics">` | `.run` | inspector |
| ReplyDraftSection.tsx:566-572 | Edit form `<select>` showing raw option ids | `RecommendationOption.id` | identifier leak |
| ReplyDraftSection.tsx:691 | decision history "· option {id}" | `snapshot.offer.option_id` | identifier leak |

Inspected: the seven inquiry-view components and `api/analysis.ts`, `api/inquiries.ts`. Not found in these files: a migration number, `StepSummary.provider`, `price_source`. `Inbox.tsx:291-328` (detail header: subject, sender, date, body) has no technical content.

Readable variant names are also S-13's outcome (`roadmap.md` S-13: "pod czytelnymi nazwami"). The plan must decide whether S-11 only drops the raw id from the metadata lines or also relabels the select and the comparison.

### Tests that assert on technical text

Counts are of expect/getBy lines that match technical text (grep; multi-line expects may be missed):

- AnalysisPanel.test.tsx: ~8. `:431-440` "Metrics" region, "1200 in / 300 out", "deterministic", list-price text; `:441,449` demo parser; `:450` "Metrics unavailable"; `:478,680` "without agents"; `:482-483,560` metric regions; `:285` "edited · model".
- ChecksSection.test.tsx: ~6. `:256-262` "without agents", "0 in / 0 out", "Checks metrics"; `:272` "Stage 1 — in parallel".
- OrchestrationSection.test.tsx: ~15. `:157-194` planner, stages, `capability → agent`, Attempts/Duration, "Orchestration metrics", wall time; `:221-227` error_type; `:256-259` rejected choice.
- RecommendationSection.test.tsx: ~10. `:138` recommender; `:141…312` "HIGH/LOW confidence"; `:142` raw option id; `:173` metrics; `:254` error code.
- PolicySection.test.tsx: 2 (`:129` option id, `:142` metrics). ReplyDraftSection.test.tsx: ~3 (`:192` metrics, `:193,201` fallback text, `:395` select value). Inbox.test.tsx: 0.

These assertions move to inspector tests or are deleted; the section tests keep their business assertions.

### i18n state

`useTranslation` is used in Inbox, AppShell, HealthFooter, LanguageSwitch and LoginForm only. None of the inquiry-view components (AnalysisPanel, Checks, Orchestration, Recommendation, Policy, ReplyDraft, RunMetrics) call `t()`; their text is hardcoded English (rough count 300+ strings). AGENTS.md requires `t()` for UI text in views that are rebuilt. New S-11 views (inspector, system page, nav) must be fully translated. Translating the remaining business sections is S-12's rebuild.

### Legacy CSS

- Layer order `index.css:6`: `theme, base, legacy, components, utilities`; `legacy.css` imported into `layer(legacy)` at `:10`.
- Compat block `legacy.css:678-775`. Every selector is `:where(.inbox__detail) :where(X)`, so it has zero specificity. It covers:
  - headings bold + margins (`:686-719`)
  - `ul`/`ol` margins, padding and markers (`:720-740`)
  - `dl` / `dd` (`:741-748`) and `pre` (`:749`)
  - **button** look (`:754-768`), checkbox margin (`:769`), textarea resize (`:773`)
- Dependents (from cascade reading, not a render):
  - Classless `<button>`s: AnalysisPanel `:569,572,580,583,633,646,654`; Checks `:349,358`; Orchestration `:259,267`; Policy `:131,139`; Recommendation `:240,248`; ReplyDraft `:194-272,474,477,634,637`.
  - h3 bold for `detail__subject` (`Inbox.tsx:307`) and `analysis__heading` (`AnalysisPanel.tsx:625`).
  - `ul` discs for `.checks__reasons` (Checks `:152`, Orchestration `:202`).
  - The checkbox at AnalysisPanel `:222` and the textareas at ReplyDraft `:462,622`.
  - `dl`, `dd` and `pre` rules are already overridden by their own classes.
- Dead after S-11 if HealthFooter and RunMetrics leave: `.status*` `:53-107`, `.metrics__steps` `:259`, `.metrics__step` `:267`, `.metrics__step--total` `:273`, `.metrics__name` `:277`.
- Still live: `.metrics__list` `:283-299` (used by Checks `:121,175`, Orchestration `:152`, Recommendation `:144`, ReplyDraft `:322,680`). `.orchestration*` `:423-478` is borrowed as a base class by Policy (`:114`), Recommendation (`:221`) and ReplyDraft (`:177,655`); if OrchestrationSection loses its technical parts, its block must stay for those users.
- `ui/` has badge, button, card, input, label. There is no Sheet, Dialog, Tabs, Table or Separator; an inspector drawer needs `npx shadcn@latest add sheet` (and the AGENTS.md post-add checks).

## Code References

- `frontend/src/App.tsx:11-16,26-41,93-102`: session-driven view switch, HealthFooter mount.
- `frontend/src/components/AppShell.tsx:13,21,30`: nav slot, widths.
- `frontend/src/components/Inbox.tsx:78,97-109,291-328`: selection state, detail fetch, `.inbox__detail` root.
- `frontend/src/components/RunMetrics.tsx:10-58`: per-step and total metrics (renders `step.kind` → "deterministic").
- `frontend/src/components/HealthFooter.tsx:19-35`: status footer.
- `frontend/src/api/analysis.ts:40-76,239-267,1128-1155`: run and orchestration types, analysis fetchers.
- `frontend/src/api/health.ts`: health client.
- `frontend/src/styles/legacy.css:53-107,259-299,423-478,678-775`: status, metrics, orchestration, compat block.
- `frontend/src/kitchen-sink.tsx:49-117,169-224,368-379`: fetch stub, state matrix, HealthFooter cell.
- `backend/app/main.py:13-20,25-47`: protected vs public routers, SPA fallback.
- `backend/app/api/health.py`, `backend/app/api/runs.py:18-33`, `backend/app/tracing/summary.py:91-153`.
- `AGENTS.md` "Frontend UI": token-only scan list (add the new views), kitchen sink, no new legacy rules.

## Architecture Insights

- **One payload, many views.** Every section already returns the full `Analysis` after a mutation, and the inspector can read the same object. If the inspector is a child route of the inquiry, it can share the inquiry's loaded `Analysis` instead of refetching. If it lives at its own URL that is opened cold, it fetches `GET /api/inquiries/{id}/analysis` itself.
- **Business/technical split follows data, not components.** OrchestrationSection mixes both: its findings (`resultLines`) feed the decision, while plan, agents and metrics are diagnostics. RunMetrics is purely technical. The natural cut is "remove RunMetrics and diagnostic lines from sections; render plan + all runs in an inspector component fed by `Analysis`".
- **Auth gating is client-side.** Every data endpoint except health is behind `get_current_user` (401). The system page needs no new backend auth, because the PRD rule concerns the UI, and `/api/health` is meant to stay public.
- **CSS migration is by deletion.** AGENTS.md forbids new legacy rules; the compat block is to be deleted with its views, not tuned. New S-11 UI uses tokens + `ui/` only and goes into the AGENTS.md scan list.

## Historical Context (from prior changes)

- `context/archive/2026-11-16-design-system-i18n-foundation/plan.md:39-40`: inquiry-view rebuild and HealthFooter move are out of F-03 scope, assigned to S-11/S-12. Supported (current code matches).
- Same `plan.md:121,517`: compat block "delete in S-11/S-12", deleting `legacy.css` incrementally. Supported; the block header at `legacy.css:684` says the same.
- Same `plan-brief.md:32`: HealthFooter hidden for anonymous now, moved in S-11. Supported (`App.tsx:102`).
- Same `plan.md:308`: AppShell "nav slot for S-11 and S-15". Supported (`AppShell.tsx:13`).
- `follow-ups/review-fixes.md`: only F6 → S-14. **No S-11 follow-up exists**; F5 (dates) is FIXED per `reviews/impl-review.md`.
- `context/foundation/tech-stack.md` "Frontend → Parked": TanStack Router for S-17. S-11 pulls it forward because S-11 is where routing first enters (`roadmap.md:104`, S-17 risk note).
- `context/audits/ux/2026-11-16-prism-analysis-flow.md` risk row 2: "Run inspector" panel (Sheet) + `/system` page; Competitive Patterns: "Run inspector as a Sheet/route, not inline".

## Related Research

- `context/archive/2026-11-16-design-system-i18n-foundation/research.md`: shell audit, deferral of HealthFooter (`:92`).

## Open Questions (for `/10x-plan`)

1. **Router flavour.** TanStack Router with code-based routes (no generator, small tree) or the Vite file-route plugin (`@tanstack/router-plugin`, generated `routeTree.gen.ts`)? Code-based adds no build step and keeps TS 7/Vite 8 risk low.
2. **Inspector shape and URL.** US-03 says "without leaving the inquiry", the audit suggests a Sheet, and FR-020 wants its own URL. One candidate is `/inquiries/$inquiryId/run` rendering a shadcn Sheet over the inquiry route. A full page at the same URL is the alternative.
3. **How much of the inquiry URL lands in S-11.** The inspector URL needs `/inquiries/$inquiryId`, which turns the `Inbox` selection into a route param. Step-in-URL and explicit return-after-login stay S-17. Do we keep the implicit "login renders in place, URL is kept" behaviour now?
4. **Identifier leaks outside metrics.** Does S-11 remove the raw variant ids, the `HIGH` enum, "without agents", "edited · model" and the demo-parser banner from the business layer, or leave the relabelling to S-12 and S-13? FR-015 counts all of them as technical identifiers.
5. **Compat block scope.** A full delete requires converting about 25 inquiry-view buttons to `Button` (S-12 territory). The S-11 options are: (a) delete only dead `.status*` / `.metrics__step*` and the compat rules no remaining element needs; or (b) convert the buttons now and delete the whole block.
6. **System page content.** Is the system page just API / database / migration from `/api/health`, or should it also show LLM provider and mailbox configuration? The latter needs a new protected endpoint.
7. **Navigation.** What does the AppShell nav slot show in S-11 (Inbox · System), and where is the inspector entry point ("How was this calculated?" in the inquiry header)?
