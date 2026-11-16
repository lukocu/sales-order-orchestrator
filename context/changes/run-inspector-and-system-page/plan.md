# Run inspector and system page (S-11) Implementation Plan

## Overview

Introduce client-side routing (TanStack Router, code-based routes) and use it for two new views of the technical layer (PRD FR-015). The **system page** at `/system` replaces `HealthFooter`. The **run inspector** is a Sheet at `/inquiries/$inquiryId/run` over the inquiry view and shows the orchestrator plan, the steps of every run with tokens, cost and time, and the totals. The salesperson's flow loses every diagnostic block and technical identifier, and the `.inbox__detail` Preflight compatibility block is deleted once the inquiry view's buttons use the shadcn `Button`. This is roadmap item S-11 (M-2).

## Current State Analysis

From `context/changes/run-inspector-and-system-page/research.md`:

- **No router.** `frontend/src/App.tsx:26` picks the view from the session; `Inbox.tsx:78` keeps `selectedId` in state. A reload loses the selected inquiry. `AppShell.tsx:13` reserves a `nav` slot for S-11/S-15.
- **Server is ready for deep links.** `backend/app/main.py:31-40` returns `index.html` for every non-`/api` path that is not a static file (test: `backend/tests/test_spa.py:21-27`). The Vite dev server falls back to HTML by default.
- **Inspector data already loads with the inquiry.** `GET /api/inquiries/{id}/analysis` returns `Analysis`, which holds six `run: RunSummary | null` fields (`api/analysis.ts:487,150,267,339,367,441`) and the orchestration plan (`OrchestrationView`, `analysis.ts:239-267`). Each section keeps only its latest run.
- **System status** comes from the public `/api/health` (`backend/app/api/health.py`): `{status, database, migration}`. `HealthFooter` renders it only when signed in (`App.tsx:102`) and is styled by legacy `.status*` (`legacy.css:53-107`).
- **Diagnostics in the business flow:** `RunMetrics` in six sections (AnalysisPanel `:591`, Checks `:429`, Orchestration `:317`, Policy `:199`, Recommendation `:314`, ReplyDraft `:351`). Further sites are listed in the research inventory: ChecksSection inline totals, plan stages, `capability → agent`, planner and recommender names, `error_type`, raw variant ids in 5 places, the `HIGH` enum, "without agents", "edited · model" and the demo-parser banner.
- **Compat block** `legacy.css:678-775` mostly gives about 25 classless `<button>`s their look. It also restores h3 bold, `ul` discs for `.checks__reasons`, the checkbox margin and textarea resize.
- **F-03 follow-ups:** none is marked S-11 (`follow-ups/review-fixes.md` has only F6 → S-14). The inherited S-11 work is the two F-03 deferrals: move HealthFooter and delete the compat block.
- **Tests:** Vitest + jsdom, English pinned (`src/test/setup.ts`). About 45 assertions on technical text across the section tests. `App.test.tsx:291-307` asserts the health footer. The kitchen sink renders `<App />` standalone in 3 cells (`kitchen-sink.tsx:358,377,403`).

## Desired End State

- `/` shows the inbox; `/inquiries/42` shows the inbox with inquiry 42 open, and a reload keeps it; `/inquiries/42/run` additionally opens the run inspector Sheet; `/system` shows the system page; any other path shows a translated "page not found" with a link to the inbox.
- Without a session, every one of these URLs renders the sign-in form in place, and the URL is unchanged. After signing in, the user lands on that URL.
- The header nav (signed in only) has links to the inbox ("Skrzynka" / "Inbox") and the system page ("System"). The active link carries `aria-current="page"`.
- The inquiry view has a "Jak to policzono?" / "How was this calculated?" link when an analysis exists. It opens the inspector, and closing the inspector (Esc, close button, overlay) returns to `/inquiries/$id` with focus back on the link.
- The inspector shows, per available run (Parsing, Checks, Orchestration, Recommendation, Policy, Reply draft): each step's name, kind, model, tokens, cost, duration and failure, plus the run totals. Orchestration adds the plan: planner, summary, stages with parallel tasks, dependencies, agent, reason, attempts and errors. A grand total across runs closes the panel. All text goes through `t()` in PL and EN.
- The inquiry view shows no `RunMetrics`, no tokens or cost, no agent, planner, recommender or model-provider names, no `deterministic`, no raw variant ids and no uppercase confidence enum. The sign-in screen shows no system status (already true; covered by a test).
- `HealthFooter.tsx`, `RunMetrics.tsx`, legacy `.status*`, `.metrics__steps/__step/__step--total/__name` and the whole `.inbox__detail` compatibility block are deleted. All inquiry-view buttons are the shadcn `Button`.
- Lint, typecheck, tests and build pass. The AGENTS.md colour scan prints nothing for the extended file list.

### Key Discoveries:

- `tech-stack.md` "Frontend → Parked" already chose TanStack Router (for S-17); S-11 pulls it forward. `@tanstack/react-router` 1.170.46 declares peer `react >=18 || >=19`.
- TanStack docs: code-based tree via `createRootRoute` / `createRoute({ getParentRoute, path })`; `createMemoryHistory({ initialEntries })` + `createRouter({ routeTree, history })` for non-browser rendering; type registration via `declare module '@tanstack/react-router' { interface Register { router: … } }`.
- `OrchestrationSection.tsx:121-126` (`taskDuration`) already joins `TaskOutcome.steps` to run step names; `:128-139` already groups tasks into stages. Both move to the inspector.
- `format.ts` already has `formatMs`, `stepCost`, `totalCost`, `totalDuration` (used by `RunMetrics`) and a locale-aware date formatter.
- `RecommendationSection.tsx` has a `KIND` map (`:139`) from `OptionKind` to a readable label; it is reusable for the variant label.
- `.metrics__list` (`legacy.css:283-299`) and `.orchestration*` (`:423-478`) stay: other sections borrow them.

## What We're NOT Doing

- **Run history.** The inspector shows the latest run of each section, the one referenced by `Analysis`. Older `trace_runs` rows are not listed, and there is no new backend endpoint.
- **Backend changes.** The system page uses the existing public `/api/health`. It shows no LLM-provider, mailbox or version info.
- **Explicit `?redirect=` after sign-in, steps in the URL, the supervisor queue route.** These are S-17 and S-15. S-11 keeps the URL by rendering sign-in in place.
- **Readable variant names and side-by-side comparison** (S-13). S-11 only removes raw ids. The Edit form's option select gets an interim label (kind + value), replaced in S-13.
- **Translating the untouched text of the six inquiry sections, and the step layout** (S-12). Only text this change adds or rewrites goes through `t()`. The sections are not added to the AGENTS.md scan list.
- **Translating backend-supplied messages** (S-16).
- **Focus handling on sign-out** (F6, S-14).
- **Playwright / E2E.** Verification is Vitest + kitchen sink + manual browser check.

## Implementation Approach

Five phases, each green on its own and committed separately.

1. Phase 1 lays the router underneath today's screens without changing what they show, except that the selected inquiry now lives in the URL.
2. Phase 2 moves system status onto its route.
3. Phase 3 adds the inspector next to the existing inline metrics, so nothing is lost mid-change.
4. Phase 4 deletes the inline diagnostics, which by then have a home.
5. Phase 5 is a pure styling migration: buttons to `Button`, then the compat block is deleted.

**Session ownership.** The session state machine (`loading | anonymous | authenticated | error`) stays in `App`, which becomes the root route component. It renders `AppShell` and either the sign-in form, the error card or `<Outlet />`. Because sign-in renders in place, the URL survives sign-in without a redirect. `beforeLoad` guards are not used in S-11.

**Inspector placement.** The inspector renders inside `AnalysisPanel`, which owns the loaded `Analysis` and replaces it after every mutation. It opens while the run route matches, so it never refetches and always shows the same data as the page.

## Critical Implementation Details

- **Timing & lifecycle.** `App`'s `fetchMe` effect must keep running once per mount under the router. The root route component must not remount on navigation, so session state goes in the root component, not in a child route. A 401 from any view still calls `handleSignedOut`, which renders sign-in in place and keeps the current URL.
- **User experience spec.** The Sheet (Radix Dialog) returns focus to its trigger on close. On a cold open of `/inquiries/$id/run` there is no trigger yet, so close navigates to `/inquiries/$id` and moves focus to the "How was this calculated?" link explicitly. The Sheet's title is the accessible name ("Inspektor przebiegu" / "Run inspector"). While `analysis` is loading it shows a loading line. If the inquiry has no analysis it says so, with no error.
- **State sequencing.** `selectedId` becomes the `inquiryId` route param, parsed as a positive integer. A non-numeric or non-positive param renders the not-found view rather than firing a request. Clicking a list row navigates (`/inquiries/$id`) instead of setting state. `AnalysisPanel` stays keyed by inquiry id.

## Phase 1: Router and inquiry address

### Overview

Add TanStack Router with a code-based route tree, make `App` the root layout, move the selected inquiry into the URL, add the header nav and a not-found view. Visible content is otherwise unchanged.

### Changes Required:

#### 1. Dependency

**File**: `frontend/package.json`, `frontend/package-lock.json`

**Intent**: Add the router chosen in `tech-stack.md`.

**Contract**: `@tanstack/react-router` as a runtime dependency, exact minor pinned by the lockfile. No `@tanstack/router-plugin`, no `routeTree.gen.ts`, no devtools in the bundle.

#### 2. Route tree and router factory

**File**: `frontend/src/router.tsx` (new)

**Intent**: One place that defines the routes and builds a router, so the app, the tests and the kitchen sink share it.

**Contract**: `createAppRouter(history?: RouterHistory)` returns a router over:
- the root route, whose component is `App` (layout and session gate);
- `/`, which renders the inbox with no selection;
- `/inquiries/$inquiryId`, which renders the inbox with that inquiry open;
- `/inquiries/$inquiryId/run`, a child of the inquiry route with no component of its own in this phase (Phase 3 makes it open the inspector);
- `/system`, a placeholder in this phase and the system page in Phase 2;
- a root `notFoundComponent`.

Type registration via `declare module '@tanstack/react-router' { interface Register { router: ReturnType<typeof createAppRouter> } }`. No route path starts with `/api`.

#### 3. Entry point

**File**: `frontend/src/main.tsx`

**Intent**: Render the router instead of `App`.

**Contract**: `<RouterProvider router={createAppRouter()} />` inside `StrictMode`; i18n import unchanged.

#### 4. App as root layout

**File**: `frontend/src/App.tsx`

**Intent**: Keep the session state machine and sign-out handling, and replace the hardcoded `<Inbox />` with `<Outlet />`. `HealthFooter` stays here until Phase 2. Remove the "No router" comment.

**Contract**: When authenticated, it renders `AppShell` with `nav` and `<Outlet />`. `onUnauthorized` reaches the routed views through a small React context (`SessionContext` with `user` and `onUnauthorized`), replacing the prop drill from `App`. Anonymous, loading and error states render as today without the outlet.

#### 5. Inbox driven by the route

**File**: `frontend/src/components/Inbox.tsx`

**Intent**: The selected inquiry comes from the route param, and selecting a row navigates.

**Contract**: The component reads an optional `selectedId: number | null` prop, which the route components pass after parsing the param. The row button becomes a `Link` to `/inquiries/$inquiryId`, keeping `aria-current` on the selected row. `user` and `onUnauthorized` come from `SessionContext`. Fetch and detail logic is unchanged.

#### 6. Header navigation

**File**: `frontend/src/components/AppNav.tsx` (new), used by `App` through `AppShell`'s `nav` slot

**Intent**: Links to the inbox and the system page for signed-in users.

**Contract**: Two TanStack `Link`s (`/`, `/system`) styled with token classes, solid focus ring, `aria-current="page"` on the active one. The inbox link is active on `/` and on `/inquiries/*`. Labels `nav.inbox`, `nav.system` and the landmark name `nav.label` go in both locales.

#### 7. Not-found view

**File**: `frontend/src/components/NotFound.tsx` (new)

**Intent**: A translated message for unknown paths and invalid inquiry ids, with a link back to the inbox.

**Contract**: Keys `notFound.heading`, `notFound.body`, `notFound.back` in both locales. It is used as the root `notFoundComponent` and for an invalid `inquiryId`.

#### 8. Tests and kitchen sink

**File**: `frontend/src/test/renderWithRouter.tsx` (new), `frontend/src/App.test.tsx`, `frontend/src/components/Inbox.test.tsx`, `frontend/src/kitchen-sink.tsx`

**Intent**: Render through the real route tree on memory history.

**Contract**:
- `renderWithRouter(path)` builds `createAppRouter(createMemoryHistory({ initialEntries: [path] }))`, renders `RouterProvider` and returns the router (for `router.state.location`).
- New tests:
  - a deep link `/inquiries/1` opens that inquiry;
  - clicking a row changes the location;
  - `/nope` and `/inquiries/abc` show not-found;
  - an anonymous visit to `/inquiries/1` shows sign-in, the location stays `/inquiries/1`, and after sign-in the inquiry shows;
  - the nav marks the active link.
- Kitchen sink: its `<App />` cells render through `createAppRouter` with memory history, and one cell adds the nav.

#### 9. Rules

**File**: `AGENTS.md`

**Intent**: Keep the colour scan covering new views.

**Contract**: Add `AppNav` and `NotFound` to the scan's file list.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- Router tests for deep link, row navigation, not-found, in-place sign-in keeping the URL, and active nav pass: `cd frontend && npx vitest run src/App.test.tsx src/components/Inbox.test.tsx`
- No router code generator or devtools in the bundle: `grep -E "router-plugin|router-devtools" frontend/package.json` prints nothing
- AGENTS.md colour scan with the extended list prints nothing

#### Manual Verification:

- In `npm run dev`, selecting an inquiry changes the URL, reload keeps it, and back/forward move between inquiries
- Signed out, opening `/inquiries/<id>` shows sign-in; after signing in the same inquiry is open
- Nav links work by keyboard with a visible focus ring, in PL and EN, light and dark

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: System page

### Overview

`/system` shows API, database and migration status from `/api/health` on token styling. `HealthFooter` and its legacy CSS are removed.

### Changes Required:

#### 1. System page

**File**: `frontend/src/components/SystemPage.tsx` (new), replacing `frontend/src/components/HealthFooter.tsx` (deleted)

**Intent**: The same data as the footer, as a page: heading, overall status (ok / degraded / unavailable as a badge with a word, not colour alone), API / database / migration, and a "Refresh" button that refetches.

**Contract**:
- Uses `fetchHealth` (`api/health.ts`, unchanged) with abort on unmount.
- shadcn `Card`, `Badge` and `Button` with token classes only.
- Status changes are announced in a `role="status"` region.
- Reuses the existing `health.*` keys and adds `health.refresh` and `system.title` in both locales.
- The route `/system` renders it.

#### 2. Shell cleanup

**File**: `frontend/src/App.tsx`, `frontend/src/styles/legacy.css`

**Intent**: Remove the footer from the shell and delete its dead CSS.

**Contract**: No `HealthFooter` import or render; delete `.status*` (`legacy.css:53-107`).

#### 3. Tests and kitchen sink

**File**: `frontend/src/components/SystemPage.test.tsx` (replacing `HealthFooter.test.tsx`), `frontend/src/App.test.tsx`, `frontend/src/kitchen-sink.tsx`, `AGENTS.md`

**Intent**: Cover the page's states and the access rule.

**Contract**:
- Tests:
  - ok, degraded (503 body), unreachable, and refresh;
  - `/system` while anonymous shows sign-in and does not call `/api/health`;
  - the inbox no longer renders a status heading.
- `App.test.tsx:291-307` is rewritten to these rules.
- Kitchen sink: system page cells for default (ok), degraded, error and loading.
- `SystemPage` is added to the AGENTS.md scan list.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- No reference to the old footer or its CSS remains: `grep -rnE "HealthFooter|\.status(__|--|\b)" frontend/src` prints nothing
- AGENTS.md colour scan with `SystemPage` prints nothing

#### Manual Verification:

- `/system` in PL and EN, light and dark, at 1440 and 375 px: readable, status word visible, Refresh works with keyboard
- The sign-in screen and the inbox show no system status or migration number

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Run inspector

### Overview

A Sheet at `/inquiries/$inquiryId/run` shows the orchestrator plan, every run's steps and totals, and a grand total. In this phase it is added next to the existing inline metrics.

### Changes Required:

#### 1. shadcn components

**File**: `frontend/src/components/ui/sheet.tsx`, `frontend/src/components/ui/table.tsx` (via `npx shadcn@latest add sheet table`)

**Intent**: A drawer and a table on the design-system contract.

**Contract**: After adding, apply the AGENTS.md checks:
- `@/lib/utils` imports;
- no `cn` package, no `baseUrl`, no `.dark` block or oklch rewrite of `index.css`;
- `focus-visible:ring-ring/50` replaced with a solid `focus-visible:ring-ring`;
- the overlay colour uses a token (no literal `bg-black/50`).

#### 2. Inspector component

**File**: `frontend/src/components/RunInspector.tsx` (new), with small subcomponents in the same folder as needed

**Intent**: Render the technical layer of one inquiry from its `Analysis`.

**Contract**:
- Props: `analysis: Analysis | null`, `loading: boolean`, `open: boolean`, `onClose()`.
- Content, in flow order, one section per non-null run: Parsing (`Analysis.run`, plus the extractor name), Checks, Orchestration, Recommendation (plus recommender name and choice error code), Policy, Reply draft. A missing run says "not run yet".
- Each run shows a step table (name, kind llm/deterministic, model, tokens in/out, cost, duration, failure with `error_type`) and a totals row.
- Orchestration also shows the plan:
  - planner name and summary;
  - stages in order, marking "in parallel" when a stage has more than one task;
  - per task: capability, agent, `depends_on`, reason, status, attempts, duration (logic moved from `OrchestrationSection.tsx:121-139`), error type;
  - planner error code / rejected planner choice when present.
- The grand total sums the input/output tokens of all present runs. Cost is the sum, marked incomplete when any run's `cost_complete` is false. Duration is the sum of run durations.
- All text through `t()` under an `inspector.*` namespace in both locales. Numbers and costs use `format.ts`.

#### 3. Route and entry point

**File**: `frontend/src/router.tsx`, `frontend/src/components/AnalysisPanel.tsx`

**Intent**: Open the inspector from the inquiry view and at its own URL.

**Contract**:
- The run route has no component of its own. `AnalysisPanel` checks whether the run route matches (`useMatch({ from: <run route id>, shouldThrow: false })`) and renders `<RunInspector open …>` with its current `analysis` state.
- A `Link` labelled `inspector.open` ("Jak to policzono?" / "How was this calculated?") sits in the analysis header when an analysis exists.
- Close navigates to `/inquiries/$inquiryId` and returns focus to that link.

#### 4. Tests and kitchen sink

**File**: `frontend/src/components/RunInspector.test.tsx` (new), `frontend/src/components/AnalysisPanel.test.tsx`, `frontend/src/kitchen-sink.tsx`, `AGENTS.md`

**Intent**: Prove the content and the URL behaviour.

**Contract**:
- RunInspector unit tests, reusing the fixtures in `src/test/*Fixtures.ts`:
  - per-run steps and totals;
  - plan stages with parallel marking and dependencies;
  - a failed task with `error_type`;
  - a missing run;
  - grand total with incomplete cost;
  - EN strings.
- Routed tests:
  - the link opens the Sheet and changes the URL to `/run`;
  - a deep link `/inquiries/1/run` opens it after the analysis loads;
  - Esc or close returns to `/inquiries/1` with focus on the link.
- Kitchen sink: inspector cells for default, loading, empty (no analysis) and error (a failed task), stubbing `GET /api/inquiries/:id` and `/analysis` with fixtures.
- `RunInspector` is added to the AGENTS.md scan list.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- Inspector unit and routed tests pass: `cd frontend && npx vitest run src/components/RunInspector.test.tsx src/components/AnalysisPanel.test.tsx`
- The generated ui files carry no 50% focus ring and no literal colours: `grep -nE "ring-ring/50|bg-black|text-white" frontend/src/components/ui/sheet.tsx frontend/src/components/ui/table.tsx` prints nothing
- Every `inspector.*` key exists in both locales (the existing key-parity test passes)
- AGENTS.md colour scan with `RunInspector` prints nothing

#### Manual Verification:

- On an inquiry with orchestration, the inspector shows the plan by stage, every run's steps and the grand total, in PL and EN, light and dark
- The Sheet traps focus, Esc closes it, focus returns to "How was this calculated?", and reload on the `/run` URL reopens it
- At 375 px the Sheet fills the width and the step table scrolls horizontally inside the panel, with no page scroll

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Clean business layer

### Overview

Remove diagnostics and technical identifiers from the six inquiry sections; the inspector is now their only home.

### Changes Required:

#### 1. Remove inline metrics

**File**: `AnalysisPanel.tsx`, `ChecksSection.tsx`, `OrchestrationSection.tsx`, `PolicySection.tsx`, `RecommendationSection.tsx`, `ReplyDraftSection.tsx` (all in `frontend/src/components/`); delete `RunMetrics.tsx`

**Intent**: No tokens, costs, durations or step lists in the business flow.

**Contract**: Remove every `<RunMetrics>` usage (6), the ChecksSection standard-banner totals (`:120-133`), and the orchestration wall-time line (`:318`). Delete `RunMetrics.tsx` and the legacy rules `.metrics__steps`, `.metrics__step`, `.metrics__step--total` and `.metrics__name` (`legacy.css:259-282`); keep `.metrics__list`.

#### 2. OrchestrationSection keeps findings only

**File**: `frontend/src/components/OrchestrationSection.tsx`

**Intent**: The salesperson sees what the checks found, not how they were planned.

**Contract**:
- Keep: the status banner (renamed to business wording, e.g. "Dodatkowe sprawdzenia" / "Additional checks"), substitute consent and its warning, the stale notice and the re-run button, and per-task findings (`resultLines`).
- Each task's heading becomes a readable label for its capability. This is a `t()` map of the known capability slugs with a generic fallback; the agent name is no longer shown.
- A failed or skipped task says the check is unavailable, without `error_type`.
- Remove: the stage grouping and titles, planner summary and name, reason, attempts, duration, ErrorBox codes and the rejected planner choice. A planner failure shows one business sentence plus the inspector link.

#### 3. Identifiers and jargon

**File**: `AnalysisPanel.tsx`, `ChecksSection.tsx`, `RecommendationSection.tsx`, `PolicySection.tsx`, `ReplyDraftSection.tsx`

**Intent**: Fulfil FR-015's "no technical identifiers in the business layer".

**Contract**:
- Remove the "Option → raw id" row (Recommendation `:145-146`) and the "· option {id}" suffixes (Policy `:163`, ReplyDraft `:304`, decision history `:691`).
- The Edit form option select (ReplyDraft `:566-572`) labels each option `{KIND label} · {value}`. This is interim until S-13; the `value` attribute stays the option id.
- The confidence band shows a readable label (high / medium / low confidence) instead of the uppercase enum.
- "· recommender {name}" (`:279-280`) is removed. The recommender error code goes to the inspector, and the section shows one business sentence.
- "completed without agents" (Checks `:119`) becomes business wording without "agents".
- The demo-parser banner (AnalysisPanel `:457-458`) moves to the inspector's Parsing section.
- "edited · model: X" (AnalysisPanel `:211-214`) becomes "edited · originally: X".
- The draft fallback notice (ReplyDraft `:307-310`) keeps its meaning without the word "model".
- Every rewritten string goes through `t()` with keys in both locales.

#### 4. Tests follow the split

**File**: the six section test files, `frontend/src/components/RunInspector.test.tsx`

**Intent**: Business tests assert business text; technical assertions live with the inspector.

**Contract**:
- Delete or move the technical assertions listed in research ("Tests that assert on technical text"); the inspector tests already cover their data.
- Add negative assertions per section: no "in / … out", no `deterministic`, no agent or planner name, no raw option id (`stock+`), no "Metrics" region.
- Add a positive test for the interim select label and the readable confidence label.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- No metrics component or dead metrics CSS remains: `grep -rnE "RunMetrics|metrics__step|metrics__name" frontend/src` prints nothing
- The sections no longer render agent, planner or recommender fields: `grep -nE "task\.agent|\.planner\b|planner_choice|\.recommender\b|option_id\}|\{option\.id\}" frontend/src/components/{AnalysisPanel,ChecksSection,OrchestrationSection,PolicySection,RecommendationSection,ReplyDraftSection}.tsx` prints nothing (the select's `value={…id}` attribute excepted)
- Section negative assertions pass: `cd frontend && npx vitest run src/components`

#### Manual Verification:

- On the ACME-style exception inquiry, the inquiry page shows no metric cards, agent, planner or recommender names, `deterministic` or raw variant ids, while the inspector still shows all of them
- The page is visibly shorter than before; record the page height at 1440 px against the audit's 10 031 px
- The Edit form's option select is understandable without ids

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 5: Remove the compatibility block

### Overview

Convert the inquiry view's raw buttons to the shadcn `Button`, give the few elements that rely on restored defaults token classes, delete `legacy.css:678-775`, and update the docs.

### Changes Required:

#### 1. Buttons

**File**: `AnalysisPanel.tsx`, `ChecksSection.tsx`, `OrchestrationSection.tsx`, `PolicySection.tsx`, `RecommendationSection.tsx`, `ReplyDraftSection.tsx`

**Intent**: Every action uses the design-system button. Its variant follows the action's role, which partly anticipates S-12's hierarchy without reordering anything.

**Contract**: Every `<button>` becomes `<Button>`, keeping the existing `type`, handlers, `disabled` and labels:
- `default` for the confirm/submit action in each form or confirmation;
- `destructive` for Reject;
- `outline` for everything else (re-run, edit, cancel, save corrections).

#### 2. Elements relying on restored defaults

**File**: `frontend/src/components/Inbox.tsx`, `AnalysisPanel.tsx`, `ChecksSection.tsx`, `OrchestrationSection.tsx`, `ReplyDraftSection.tsx`

**Intent**: Keep the look the block provided, using utilities.

**Contract**:
- `font-bold` on `detail__subject` (`Inbox.tsx:307`) and `analysis__heading` (`AnalysisPanel.tsx:625`).
- `list-disc ps-5` on `.checks__reasons` lists.
- Token-class margin on the correction checkbox (`AnalysisPanel.tsx:222`).
- `resize-y` on the textareas (`ReplyDraftSection.tsx:462,622`).

#### 3. Delete the block

**File**: `frontend/src/styles/legacy.css`

**Intent**: Close the F-03 deferral.

**Contract**: Delete `legacy.css:678-775`, including the comment and the "delete in S-11/S-12" header. `.inbox__detail` stays only as a class name if still useful for layout; no rule targets it via `:where()`.

#### 4. Documentation

**File**: `AGENTS.md`, `context/foundation/tech-stack.md`

**Intent**: Docs match the code.

**Contract**:
- AGENTS.md "Legacy CSS": drop the `.inbox__detail` compatibility sentence; note that the remaining legacy rules serve the inquiry sections until S-12.
- tech-stack.md "Frontend": move TanStack Router from "Parked" to the in-use list (code-based routes, `src/router.tsx`, introduced in S-11).
- Fix "until S-12 removes it" if wording changed.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- The compat block is gone: `grep -n "inbox__detail" frontend/src/styles/legacy.css` prints nothing
- No raw buttons remain in the inquiry view: `grep -nE "<button\b" frontend/src/components/{AnalysisPanel,ChecksSection,OrchestrationSection,PolicySection,RecommendationSection,ReplyDraftSection,Inbox}.tsx` prints nothing
- Docs updated: `grep -n "TanStack Router" context/foundation/tech-stack.md` shows it outside "Parked", and `grep -n "compatibility block" AGENTS.md` prints nothing

#### Manual Verification:

- Visual check of the full inquiry flow (parse → checks → recommendation → policy → draft → decision) in light and dark at 1440 px and 375 px: headings bold, reasons bulleted, buttons consistent, Reject visibly destructive, focus ring visible on every button
- Screenshots of the inquiry view top and the inspector in light and dark at 1440 are saved under `context/changes/run-inspector-and-system-page/screenshots/`

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- `RunInspector` covers:
  - steps and totals per run, and the grand total with incomplete cost;
  - plan stages, parallel marking and dependencies;
  - a failed task, a missing run, and no analysis.
- `SystemPage` covers ok, degraded, unreachable and refresh.
- Sections: negative assertions for technical text; positive ones for the new business labels.

### Integration Tests:

All on memory history through `createAppRouter`:
- deep links to `/inquiries/:id`, `/inquiries/:id/run` and `/system`;
- not-found for an unknown path and an invalid id;
- an anonymous visit renders sign-in and keeps the URL, and sign-in shows the requested view;
- inspector open/close with focus return;
- the active nav link.

### Manual Testing Steps:

1. Sign out, open `/inquiries/<id>/run` directly, sign in: the inquiry with the inspector opens.
2. Walk an exception inquiry end to end; confirm no diagnostics on the page and all of them in the inspector.
3. Open `/system` in both languages and themes; stop the database (docker compose) and Refresh to see degraded.
4. Check the inquiry view and the inspector at 375 px.

## Performance Considerations

None material. The inspector reuses the already loaded `Analysis`; the router adds one dependency (~a few tens of kB gzipped), acceptable for an internal tool.

## Migration Notes

No data or backend migration. Rollback is a revert of the phase commits. Old bookmarks do not exist (no URLs before S-11).

## References

- Research: `context/changes/run-inspector-and-system-page/research.md`
- Roadmap: `context/foundation/roadmap.md` (S-11, S-17 risk note)
- PRD: FR-015, FR-005, US-03, FR-020, Access Control (`context/foundation/prd.md`)
- UX audit: `context/audits/ux/2026-11-16-prism-analysis-flow.md`
- F-03 plan and deferrals: `context/archive/2026-11-16-design-system-i18n-foundation/plan.md:39-40,121,517`
- Stage grouping and task duration to move: `frontend/src/components/OrchestrationSection.tsx:121-139`
- SPA fallback: `backend/app/main.py:25-47`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Router and inquiry address

#### Automated

- [x] 1.1 Lint, typecheck, tests and build pass
- [x] 1.2 Router tests for deep link, row navigation, not-found, in-place sign-in keeping the URL, and active nav pass
- [x] 1.3 No router code generator or devtools in the bundle
- [x] 1.4 AGENTS.md colour scan with the extended list prints nothing

#### Manual

- [x] 1.5 Selecting an inquiry changes the URL, reload keeps it, back/forward work
- [x] 1.6 Signed out deep link shows sign-in, then the same inquiry after sign-in
- [x] 1.7 Nav links work by keyboard with visible focus, PL/EN, light/dark

### Phase 2: System page

#### Automated

- [ ] 2.1 Lint, typecheck, tests and build pass
- [ ] 2.2 No reference to the old footer or its CSS remains
- [ ] 2.3 AGENTS.md colour scan with SystemPage prints nothing

#### Manual

- [ ] 2.4 /system readable in PL/EN, light/dark, 1440 and 375 px, Refresh by keyboard
- [ ] 2.5 Sign-in screen and inbox show no system status or migration number

### Phase 3: Run inspector

#### Automated

- [ ] 3.1 Lint, typecheck, tests and build pass
- [ ] 3.2 Inspector unit and routed tests pass
- [ ] 3.3 Generated ui files carry no 50% focus ring and no literal colours
- [ ] 3.4 Every inspector key exists in both locales
- [ ] 3.5 AGENTS.md colour scan with RunInspector prints nothing

#### Manual

- [ ] 3.6 Inspector shows plan by stage, every run's steps and the grand total, PL/EN, light/dark
- [ ] 3.7 Sheet traps focus, Esc closes, focus returns, reload on /run reopens
- [ ] 3.8 At 375 px the Sheet fills the width with no page scroll

### Phase 4: Clean business layer

#### Automated

- [ ] 4.1 Lint, typecheck, tests and build pass
- [ ] 4.2 No metrics component or dead metrics CSS remains
- [ ] 4.3 Sections no longer render agent, planner or recommender fields
- [ ] 4.4 Section negative assertions pass

#### Manual

- [ ] 4.5 Inquiry page shows no diagnostics while the inspector shows all of them
- [ ] 4.6 Page height at 1440 px recorded against the audit's 10 031 px
- [ ] 4.7 Edit form option select is understandable without ids

### Phase 5: Remove the compatibility block

#### Automated

- [ ] 5.1 Lint, typecheck, tests and build pass
- [ ] 5.2 The compat block is gone
- [ ] 5.3 No raw buttons remain in the inquiry view
- [ ] 5.4 Docs updated

#### Manual

- [ ] 5.5 Visual check of the full inquiry flow in light/dark at 1440 and 375 px
- [ ] 5.6 Screenshots of the inquiry view and inspector saved
