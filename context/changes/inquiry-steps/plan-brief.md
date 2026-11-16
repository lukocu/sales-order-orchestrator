# Inquiry steps (S-12) — Plan Brief

> Full plan: `context/changes/inquiry-steps/plan.md`

## What & Why

The salesperson reaches the decision only after a long single-column page: the e-mail, the form, then checks with four exception sections nested inside, the decision buttons above the check results, and the justification and policy table shown twice. PRD FR-016 and the M-2 success criterion ask for steps Zapytanie → Warianty → Akceptacja → Odpowiedź, each with data first and one primary action visible without scrolling at 1440×900. This is the M-2 north star.

## Starting Point

After S-11 the view is free of diagnostics but still one stack: `Inbox` renders the e-mail above `AnalysisPanel`, which renders the corrections form and `ChecksSection`, which hosts Orchestration, Recommendation, Policy and ReplyDraft. There is no overall status; state comes from `analysis` / `checks.outcome` / `recommendation` / `draft.status`. Nearly all text is hard-coded English.

## Desired End State

A compact header and a step bar; one step panel at a time, its primary action above the fold. Completed steps can be reopened, future ones are locked, a standard inquiry shows the last three as "not needed". The decision (salesperson and supervisor) sits in Akceptacja next to the variant, the policy verdict in force and the e-mail; Odpowiedź shows the ready-to-send result. Moving back (reject, re-analysis, stale result) is announced. The whole view works in PL and EN; no horizontal scroll at 375 px.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Active step | Derived from state; done steps viewable, future locked; step-back announced | The decision is always where the state says, context one click away | Plan |
| Standard / needs_input | Full four-step bar; standard ends at Zapytanie, others "not needed"; needs_input stays in Zapytanie | One layout; shows FR-004 "standard ends without agents" | Plan |
| Stepper form | One step at a time, shadcn Tabs on `radix-ui` (already a dependency) | Best chance for the CTA within 900 px; keyboard navigation built in | Plan |
| Where the decision is | Akceptacja: variant + policy in force + e-mail + Approve / Edit / Reject (and supervisor); Odpowiedź = result | Decision next to its justification, matches US-02 | Plan |
| Awaiting supervisor | Shown in Akceptacja (decision not finished); Odpowiedź only for ready_to_send | Odpowiedź is the end state; rejected returns to Akceptacja | Plan |
| Duplicates | Justification only in Warianty, policy table only in Akceptacja (verdict in force), shared label module | FR-016 "each piece of information once" | Plan |
| Re-runs / orchestration | Stay in their step as secondary, primary only when the result is missing/stale/failed; findings collapsible in Warianty | Keeps recovery without the inspector; no backend change | Plan |
| Translation | All UI text of the view through `t()`, EN wording unchanged; backend texts stay for S-16 | Components touched once; tests stay mostly valid | Plan |
| E-mail placement | Body in Zapytanie next to the fields; compact header above the steps; "Show e-mail" disclosure elsewhere | Keeps every step's CTA near the top | Plan |
| Verification | Vitest + kitchen sink + manual DOM gate (bounding box at 1440×900, scrollWidth at 375) | F-03/S-11 pattern; lesson "ARIA/DOM before screenshots" | Plan |

## Scope

**In scope:**
- step model and stepper;
- e-mail moved into Zapytanie;
- re-ordered steps with one primary action each;
- destructive confirmations;
- duplicates removed and shared policy labels;
- full translation of the view;
- kitchen-sink states;
- manual 1440/375 gate;
- AGENTS.md scan list;
- dead legacy CSS.

**Out of scope:**
- step in the URL (S-17);
- readable variant names and comparison (S-13);
- "Send to supervisor" label and inbox statuses (S-14);
- supervisor queue and rights (S-15);
- backend text translation (S-16);
- any API change;
- 3-pane layout;
- E2E in CI.

## Architecture / Approach

`inquirySteps(analysis)` (pure) returns the active step and a state per step. `AnalysisPanel` keeps all handlers and `busy`, holds `viewedStep`, and renders `InquirySteps` (Tabs) whose panels compose the existing sections:
- inquiry: e-mail, fields, checks;
- variants: recommendation, findings;
- approval: summary, policy, e-mail preview, decision, history;
- reply: the result.

`ChecksSection` is reduced to the checks.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Texts through `t()` | PL/EN for the whole view, shared policy labels | ~200 keys; missing a string |
| 2. Step model and stepper | Derivation + Tabs + sections in steps + e-mail move | Test nesting assertions; step-back message timing |
| 3. Zapytanie and Warianty | Data → one primary action per state | Choosing the right primary in error/stale states |
| 4. Akceptacja and Odpowiedź | Decision beside its data, no duplicates | Splitting ReplyDraftSection (32 tests) |
| 5. States, gate, cleanup | Kitchen sink, 1440/375 proof, docs, CSS | CTA may not fit 900 px in Akceptacja → collapse the e-mail |

**Prerequisites:** F-03 and S-11 merged (done, PR #5); `npx shadcn@latest add tabs` access.
**Estimated effort:** ~4–5 sessions across 5 phases (Phases 1 and 4 are the largest).

## Open Risks & Assumptions

- Akceptacja is the longest step; if the primary action does not fit within 900 px, the e-mail preview is collapsed by default (planned fallback, measured in Phase 5).
- The supervisor still can edit and re-analyse in S-12; S-15 restricts it.
- English wording stays as today until S-14 renames actions, so EN tests remain the safety net during the rewrite.

## Success Criteria (Summary)

- On 1440×900 the primary action of every step is visible without scrolling (baseline 8 051 px).
- Each piece of information appears once and the decision follows its data in reading order.
- The whole view reads in Polish or English; lint, typecheck, tests and build are green.
