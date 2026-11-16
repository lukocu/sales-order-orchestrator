---
audit: prism
mode: both (UX/UI full + WCAG 2.2 AA priority criteria)
date: 2026-11-16
scope: inbox → inquiry analysis (US-01, salesperson) and supervisor approval (US-02)
input: live app, local docker compose (http://localhost:8010), LLM_PROVIDER=fake, demo accounts `sales` / `supervisor`
viewports: 1440×900 desktop, 375×812 mobile; dark theme (prefers-color-scheme), light theme from computed tokens only
feeds: PRD amendment (information architecture), /10x-roadmap M-2, /10x-ui research for `analysis-view-ux-redesign`
---

# Prism audit — inquiry analysis flow

**Product:** Sales Order Orchestrator, a B2B internal tool for handling sales inquiries.
**Audience:** salesperson (primary), supervisor (secondary, only approves exceptions). Personas from `context/foundation/prd.md`.
**Business goal of the screen:** reply to an inquiry quickly with an offer that respects margin and deadline. For an exception, the salesperson chooses a variant and the supervisor approves only what the policy blocks.

## Measurements (evidence)

| Metric | Value | Comment |
|---|---|---|
| Page height, ACME inquiry (US-01), desktop | **10 031 px** (~11 screens of 900 px) | the whole flow is one column |
| Position of the main decision `Approve` (salesperson) | **8 051 px** from the top | ~9 screens of scrolling to the decision |
| Position of `Approve`/`Reject` (supervisor, discount inquiry) | **8 732 px** | the supervisor has no shortcut |
| Page height, mobile 375 px | **13 646 px**; analysis starts at 938 px | |
| `Metrics` blocks in the business flow | **6** (Metrics, Checks, Orchestration, Recommendation, Policy, Draft) | with the fake LLM every one shows `0 in / 0 out`, `Cost —` |
| Steps with tokens/cost/time shown, ACME | **20+ cards** | e.g. `agent:substitute-compatibility · deterministic` |
| Duplicated content | "Why this recommendation?" with its reasons ×2, policy table ×2 | in Recommendation/Policy and again in Reply draft |
| `<h4>` headings in the analysis | 12, of which 6 are "… metrics" | half of the section structure is diagnostics |
| Decision buttons | `Approve` · `Edit offer` · `Reject` with the same visual weight | `Reject` is not marked as destructive |
| Focus styles in CSS | **0 rules** `:focus` / `:focus-visible` | browser default `auto 1px` |

## 🎨 UX/UI Full Audit

### 🔴 Critical issues

1. **The decision is buried under diagnostics.** The salesperson has to scroll ~8 000 px past 20+ metric cards (`0 in / 0 out`, `Duration 0.0 ms`) to reach `Approve`. The checks that justify the decision (customer, stock, price, credit) are rendered **after** the decision buttons. · *Hick's Law, Serial Position Effect, Nielsen #8*
2. **No technical/business separation.** Agent names (`agent:supplier-availability`), `planner fake`, `recommender rule-based`, `deterministic`, the migration ID `0014_inquiry_source` (also on the sign-in screen) sit at the same level as margin and deadline. · *Nielsen #2 (match with the real world), Tesler's Law*
3. **"Approve" means two different things.** With the verdict "Requires supervisor approval" the button still says `Approve`, and the confirmation is `Comment (optional) / Confirm approval` with no information that the offer goes **to the supervisor**. After confirmation there is no notice (`role=status` empty); the status changes only in the "Reply draft" section ~8 000 px down. · *Nielsen #1 (system status), Nielsen #5 (error prevention)*
4. **No path for the supervisor.** The supervisor gets the same inbox as the salesperson; "Awaiting supervisor only (1)" is a small secondary filter button, and `Approve`/`Reject` are 8 732 px down. Meanwhile the supervisor also sees `Save corrections` and `Re-analyze` on someone else's inquiry that is awaiting a decision. · *Goal-Gradient, Jakob's Law (approval queue as in Jira/HubSpot)*

### 🟡 Moderate issues

1. **Variants are hard to compare.** The recommendation and "Other options" are vertical `dl` lists. Coverage/deadline/margin cannot be compared side by side, and the variant IDs are raw (`stock+ABC-110+supplier:Sensortech Polska`). · *Proximity, Recognition rather than recall*
2. **Mixed languages.** The UI is in English (`Approve`, `Coverage`, `Fulfilled`), while the content, the reasons ("Pokrywa całą zamówioną ilość") and the reply are in Polish, and the persona is a Polish salesperson. · *Nielsen #4 (consistency)*
3. **Inbox without status.** Only `Exception` / `Awaiting supervisor` badges; there is no "new / analysed / ready to send" state or the customer name at the start of the row. The list scrolls along with the page, so at the decision the inbox context is out of view. · *Zeigarnik Effect, Visibility of system status*
4. **Width is not used.** At 1440 px the content takes up ~half the width (two narrow columns, an empty right margin), while it is 10 000 px tall. · *Figure/Ground, Aesthetic-Usability*
5. **Everything has the same weight.** One button style (border + background = card) for `Fetch mail`, `Re-analyze`, `Approve` and `Reject`; one card style for every section. · *Von Restorff Effect, Similarity*
6. **The confirmation for `Re-analyze`** ("Corrections will be lost.") uses the same buttons as cancelling. · *Error prevention*

### 🟢 What works well
- The checks and policy have clear verdicts with words, not colour alone (`Pass`/`Fail`, `Matched`/`Insufficient`).
- The recommendation has a cited justification ("Why this recommendation?") and a confidence level, which builds trust (*Reflective*).
- Uncertain parsed fields are highlighted with the original phrase (`"do piątku"`, `"najlepszą cenę"`), a good correction pattern.
- The page has no horizontal scroll at 375 px; forms have labels; semantic `table`.
- The dark theme on tokens with good text contrast (see WCAG).

### UX Laws Analysis (most relevant)

| Law | Observation |
|---|---|
| Hick's Law | on one screen: correction (2 buttons), 3 variants, policy, draft (3 actions), 6 metric sections; no step-by-step guidance |
| Serial Position | the most important thing (decision) is in the middle-end, and the justification (checks) at the very end |
| Von Restorff | no distinguished primary action; the recommended variant differs only by its heading |
| Goal-Gradient | no progress indicator for "inquiry → offer sent" |
| Tesler's Law | complexity is not hidden: the user takes on reading the orchestration plan |
| Jakob's Law | B2B tools (HubSpot, Front, Linear) use a list + detail + right-hand context panel; here it is a long document |
| Progressive Disclosure | absent: all sections are expanded all the time |
| Fitts' Law | buttons 42 px high, fine on desktop; but the main target is distant in terms of scroll |

### Nielsen's 10 Heuristics (1 = OK, 5 = serious violation)

| # | Heuristic | Score | Observation |
|---|---|---|---|
| 1 | Visibility of system status | 4 | no feedback after approval; status deep in the page; inbox without states |
| 2 | Match with real world | 4 | agent jargon, migrations, `deterministic`, variant IDs |
| 3 | User control and freedom | 2 | Cancel/Re-analyze exist; no undo after approval |
| 4 | Consistency and standards | 3 | EN/PL mixed; one button style for different actions |
| 5 | Error prevention | 3 | `Approve` with a policy that blocks does not say what will happen |
| 6 | Recognition rather than recall | 3 | variants not comparable side by side; decision far from the data |
| 7 | Flexibility and efficiency | 4 | no queue view for the supervisor, no shortcuts, no links to an inquiry |
| 8 | Aesthetic and minimalist design | 5 | 20+ metric cards with zero values in the main flow |
| 9 | Error recognition and recovery | 2 | errors with `role=alert` and Retry |
| 10 | Help and documentation | 2 | "Why this recommendation?" explains the decision; no hints for policy rules |

### Cognitive Load
- **Intrinsic:** substantial and justified (variants × margin × deadline × policy). This is exactly why the screen should take it on for the user.
- **Extraneous:** dominant. Metrics, plan stages, duplicated reasons and policy table, the inquiry's technical identifiers.
- **Germane:** valuable in "Why this recommendation?" and in the policy table with the reason, worth keeping and showing next to the decision.

### Emotional Design (Norman)
- **Visceral:** a clean, GitHub-like dark theme that looks like a developer tool, not a sales tool.
- **Behavioral:** a lot of scrolling, no feedback after actions, the decision far from the data.
- **Reflective:** an engineer will appreciate the transparency of the orchestration (good for the portfolio); a salesperson will feel the tool "talks to itself".

### Business Goals Alignment
- The screen's goal (send a correct offer quickly) is satisfied functionally but **fights the user**: the time to decision is dominated by scrolling and filtering out diagnostics.
- The tech layer has **business value for the portfolio audience** (AI Engineer). It should not disappear, only move behind "How was this calculated?" and to `/system`.
- The supervisor (approves only exceptions) has no dedicated path, so every exception costs them the full read-through of the page.

### Competitive Patterns
- **HubSpot / Salesforce (deals):** record header with status and value, primary action in the header, details in tabs. The lesson: decision and status at the top, details below.
- **Front (shared inbox):** list + conversation + right-hand context panel; statuses on list rows. The lesson: the email next to the parsed fields, a context panel instead of a long column.
- **Linear / Jira (approvals):** a separate "awaiting me" queue with a counter in the navigation. The lesson: a "To approve" view for the supervisor.
- **Datadog / Vercel (run traces):** run traces in a separate view or drawer, available from a link. The lesson: "Run inspector" as a Sheet/route, not inline.

### Full Risk Table

| # | Issue | Law / Principle | Sev | Freq | Impact | Recommendation | Priority |
|---|---|---|---|---|---|---|---|
| 1 | Decision 8 000 px down, under the metrics | Hick, Serial Position, Nielsen 8 | 5 | every exception | time to offer, missed decision | steps (Inquiry → Variants → Approval → Reply) with the CTA at the top of each step | Immediate |
| 2 | Diagnostics (6× metrics, agents, migration) in the business flow | Nielsen 2, Tesler | 4 | every inquiry | noise, loss of trust | "Run inspector" panel (Sheet) + `/system` page; HealthFooter only for authenticated users/admin | Immediate |
| 3 | `Approve` with blocking policy without saying "goes to supervisor"; no feedback | Nielsen 1, 5 | 4 | every policy exception | wrong mental model, sending again | label "Send to supervisor", toast/status at the top, status badge in the header | Immediate |
| 4 | No queue for the supervisor | Jakob, Goal-Gradient | 4 | every approval | slow approval | "To approve" view with a counter in the navigation, decision at the top | Next sprint |
| 5 | Variants not comparable | Proximity, Recognition | 3 | every exception | harder choice | variant cards side by side (coverage, deadline, margin, risks), readable names | Next sprint |
| 6 | Duplicated reasons and policy table | Minimalist design | 3 | every draft | longer reading | one place per piece of information, references instead of copies | Next sprint |
| 7 | One button style, `Reject` not destructive | Von Restorff, Similarity | 3 | every decision | risk of a misclick | Button variants primary/secondary/destructive | Next sprint |
| 8 | EN/PL mixed | Nielsen 4 | 2 | everywhere | inconsistency | decision on the UI language (PRD) | Backlog |
| 9 | Inbox without states and context | Zeigarnik, Nielsen 1 | 3 | every session | no "what's left to do" overview | state badges, customer first, sticky list | Next sprint |
| 10 | Narrow column at 1440 px | Figure/Ground | 2 | desktop | more scrolling | 3-pane layout (list · detail · panel) | Backlog |

### Prioritized improvement plan
**Immediate (blockers):** remove diagnostics from the flow (inspector + `/system`), stepper with the CTA at the top, a clear label and feedback for "Send to supervisor".
**Next sprint:** "To approve" queue, variant cards, Button variants (shadcn), inbox statuses, no duplicates.
**Backlog:** UI language, 3-pane layout, links to an inquiry/step (router).

---

## ♿ WCAG 2.2 AA Audit (priority criteria)

The w3.org quick-reference was not fetched; criterion numbers are from WCAG 2.2 knowledge. Contrast is computed from the `:root` tokens (`frontend/src/index.css`); the light theme is verified only by calculation.

### Summary
| Status | Count |
|---|---|
| 🔴 Failures | 1 |
| 🟡 Warnings | 4 |
| 🟢 Passing | 9 |

### Findings

**1.4.11 Non-text Contrast**
Status: 🔴 Fail
Where: borders of fields (`input`, `select`) and buttons. `--border` on `--card`
Finding: dark `#3d444d` on `#151b23` = **1.76:1**; light `#d1d9e0` on `#fff` = **1.43:1**; required 3:1 for the boundary of a form field
Risk: users with low vision cannot see where the field to edit is (parse corrections)
Fix: an `--input` token with ≥3:1 contrast (e.g. dark ~`#6e7681` = ~3.6:1 on `#151b23`), used for field and button borders; `--border` stays decorative

**2.4.7 Focus Visible**
Status: 🟡 Warning
Where: all buttons and fields; `index.css` has 0 `:focus`/`:focus-visible` rules
Finding: browser default `outline: auto 1px`, visible but thin on a dark background; with background/border changes there is a risk of it disappearing
Fix: a `--ring` token and `:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px }` (shadcn: `focus-visible:ring-2 ring-ring`)

**1.3.2 Meaningful Sequence**
Status: 🟡 Warning
Where: `ChecksSection`: the check results (Customer, Stock, Price, Credit) are after the decision buttons
Finding: the reading order (and screen reader order) puts the justification after the decision
Fix: order data → recommendation → policy → decision

**1.4.10 Reflow**
Status: 🟡 Warning
Where: policy table at 375 px (`policy__table-wrap` 366/293 px)
Finding: no page scroll (a table may scroll), but the "Reason" column is hidden off screen with no signal
Fix: on mobile, the table as a list of rule cards, or a visible scroll hint

**4.1.3 Status Messages**
Status: 🟡 Warning
Where: after "Confirm approval" no `role=status` message; the status changes deep in the page
Fix: a toast/live region "Sent to supervisor" + a status badge in the inquiry header

**🟢 Passing:** 1.4.3 text contrast (dark muted 5.94:1, light muted 6.11:1, ok/warn/error ≥4.87:1), 1.4.1 colour is not the only carrier (Pass/Fail as words), 3.3.2 field labels (0 fields without a label), 1.3.1 heading hierarchy without skips (h1→h2→h3→h4) and `table` with headers, 2.1.1 keyboard (native `button`), 4.1.2 names and roles (native elements, `aria-pressed` on the filter), 3.3.1 errors with `role=alert` and text, 1.4.4 rem-based typography, 1.1.1 no images without alt.

### Violations table
| # | Criterion | Name | Severity | Location | Fix priority |
|---|---|---|---|---|---|
| 1 | 1.4.11 | Non-text Contrast | 🔴 | `--border` fields/buttons, both themes | Immediate (with the tokens phase) |
| 2 | 2.4.7 | Focus Visible | 🟡 | global, no `--ring` | Tokens phase |
| 3 | 4.1.3 | Status Messages | 🟡 | approve/send to supervisor | View phase |
| 4 | 1.3.2 | Meaningful Sequence | 🟡 | ChecksSection order | View phase |
| 5 | 1.4.10 | Reflow | 🟡 | policy table, mobile | States phase |

---

## 🔭 Combined Summary

### Top 3 issues to fix first
1. Decision buried under diagnostics (8 000 px, 6× metrics) · UX · Severity 5
2. "Approve" without information about the supervisor and without feedback (+ 4.1.3) · UX/WCAG · Severity 4
3. Field and button boundary contrast 1.76:1 + no focus token · WCAG · Severity 4 (cheap to fix in the tokens phase)

### Overall health
🎨 UX/UI: functionally complete and honest about the data, but laid out as a technical report rather than a salesperson's tool.
♿ Accessibility: good semantic foundation (native elements, labels, text contrast); gaps at the token level (field boundaries, focus) and in status messages.

## Not covered by this audit
- A real LLM (`groq`): with the fake provider the metrics show zeros; with tokens and cost they will be even more prominent.
- The light theme visually (contrast only computed), 200% zoom, a screen reader.
- The `Edit offer` / `Reject` path and errors (409 "Draft changed"), the empty inbox, Fetch mail errors.
