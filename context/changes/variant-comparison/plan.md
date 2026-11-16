# Variant comparison side by side Implementation Plan

## Overview

The **Warianty** step shows the fulfilment variants of an exception side by side in one comparison table instead of a stack of cards. Every variant has a readable name ("Stan + zamiennik ABC-110"). The recommended variant is in the first column, labelled and outlined. Rows show coverage, the date against the customer's deadline (with the difference in days), value, margin, risks and confidence. At 375 px, columns that do not fit are announced by a visible "scroll sideways" signal, so nothing is hidden silently. This is roadmap S-13: PRD FR-017, FR-007, US-01 and the NFR (375 px, tables without hidden columns). It is frontend only and changes no stored data.

## Current State Analysis

- `frontend/src/components/RecommendationSection.tsx:120-169` (`OptionCard`) renders each option as a `<dl>`: lines, coverage, fulfilment date + deadline verdict, value, cost, margin, then signals grouped as positive / risk / info. `RecommendationResult` (`:241-298`) shows the chosen option as a card (region "Rekomendowana opcja") with the justification, and the others as a list "Pozostałe opcje". These are cards stacked vertically, not side by side.
- A variant is named only by its kind: `t('optionKind.<kind>')` (`pl.json:273-278`, e.g. "Magazyn + zamiennik"). `build_options` (`backend/app/recommendation/options.py:218-295`) builds one option per substitute, one per supplier offer and one per substitute × supplier pair. With two substitutes, two options carry the same name. The distinguishing facts (substitute `product_code`, supplier name) are in `option.lines` (`OptionLine.source`, `.product_code`, `.supplier`).
- The edit-offer selector names its choices the same ambiguous way: `ReplyDraftSection.tsx:518-527` (`draft.optionLabel` = kind · value). Its choices may include the draft's current offer (`DraftOffer`: `kind`, `lines` with `source`/`supplier`/`product_code`) when the recommendation no longer lists it (`:459-464`).
- Deadline: each option has `meets_deadline: boolean | null`. The customer's expected date is `analysis.fields.deadline` (ISO or null, `api/analysis.ts:30`), and `AnalysisPanel` holds `analysis` when it renders `RecommendationSection` (`AnalysisPanel.tsx:798-811`).
- `components/ui/table.tsx` wraps tables in `relative w-full overflow-x-auto`. S-11 accepted horizontal scrolling of a table inside its panel with no page scroll (`context/archive/2026-11-16-run-inspector-and-system-page/plan.md:331`). The scrollable region has no signal today.
- S-12 rule: each piece of information appears once in the view (`context/archive/2026-11-16-inquiry-steps/plan.md:14,22`).
- AGENTS.md: token classes only, `t()` for every text in pl/en, no new legacy rules, delete a legacy rule when its last user goes, add rebuilt views to the colour-scan list, new states go into the kitchen sink.

## Desired End State

Opening the Warianty step of an exception with a completed recommendation shows:
1. the result banner and the time of the recommendation;
2. the recommended variant's name and "Dlaczego ta rekomendacja?" with the justification;
3. a comparison table. Column headers are the variant names, the recommended one first, with a "Rekomendowany" label and an accent outline. Rows are Pokrycie, Termin, Wartość, Marża, Ryzyka and Pewność;
4. one `<details>` per variant, in the same order (the recommended one open). Each holds lines, cost and all signals; cited signals stay marked.

With a failed recommendation (no choice), the columns are in build order and none is highlighted. At 375 px the attribute column stays visible, the table scrolls inside a keyboard-focusable region, and while it overflows a visible text "Wariantów: N — przewiń w bok, aby zobaczyć wszystkie" is shown. There is no page-level horizontal scroll. The edit-offer selector uses the same readable names. All texts exist in PL and EN.

### Key Discoveries:

- Readable names come from `lines`, not from parsing `option.id` (`options.py:292` shows the id format is an implementation detail).
- `DraftOffer` lines have the same `source`/`supplier`/`product_code` fields, so one function serves both `RecommendationOption` and `DraftOffer`.
- Existing tests query `region "Recommended option"` and `list "Other options"` (`RecommendationSection.test.tsx:116-178`). They are rewritten against the table and the details.

## What We're NOT Doing

- No backend, API, schema or JSONB change. `option.id` stays the stored identifier, and readable names exist only in display.
- No new data per variant (e.g. lead time per line) beyond what `RecommendationOption` carries.
- No sorting or filtering of the table by the user.
- No change to the Akceptacja/Odpowiedź steps beyond the edit-offer selector's option names.
- No cards layout below a breakpoint. The table is the only layout.
- No change to `OrchestrationSection` ("Ustalenia" details) or the run inspector.

## Implementation Approach

A pure helper produces the readable name. A new presentational component `VariantComparison` renders the table and the per-variant details from `RecommendationView` plus the expected deadline. `RecommendationSection` keeps its banners, rerun logic and states, and delegates the result body to it. Narrow-screen behaviour (sticky first column, overflow signal) comes last, so phases 1–2 can be verified at desktop width first.

## Critical Implementation Details

- **Deadline difference vs `meets_deadline`**: the day difference is computed from `fulfilled_on` and `fields.deadline` (calendar days, no time zone shift: compare ISO date strings as dates). When `fields.deadline` is null, show "brak terminu" regardless of `meets_deadline`. If the fields changed after the recommendation, the existing "stale" notice already says the result may be out of date. Do not add a second warning.
- **Overflow signal**: detect overflow as `scrollWidth > clientWidth` on the scroll container, re-evaluated with a `ResizeObserver`. jsdom has no layout, so unit tests stub the measurement or only assert that the signal is absent. The 375 px behaviour is verified in the browser (DOM/ARIA first, per lessons).

## Phase 1: Readable variant names

### Overview

One function names a variant from its kind and lines. The edit-offer selector uses it.

### Changes Required:

#### 1. Name helper

**File**: `frontend/src/components/variantName.ts` (new), `frontend/src/components/variantName.test.ts` (new)

**Intent**: Build a readable, distinguishing name for a variant so that two substitutes or two suppliers are told apart.

**Contract**: `variantName(variant: { kind: OptionKind; lines: { source: LineSource; product_code: string; supplier: string | null }[] }, t: TFunction): string`. Parts are taken in line order: a `stock` line gives `variant.stock` ("Stan" / "Stock"), a `substitute_stock` line gives `variant.substitute` ("zamiennik {{code}}" / "substitute {{code}}"), and a `supplier` line gives `variant.supplier` ("dostawca {{supplier}}" / "supplier {{supplier}}"). Parts are joined with " + " and the first letter is capitalised. A variant whose only part is stock (`partial_delivery`) is named `variant.stockOnly` ("Tylko stan (dostawa częściowa)" / "Stock only (partial delivery)"). With no lines, it falls back to `t('optionKind.<kind>')`. Examples: "Stan + zamiennik ABC-110", "Stan + dostawca Hydro-Valve", "Stan + zamiennik ABC-110 + dostawca Hydro-Valve", "Zamiennik ABC-110" (no own stock).

#### 2. i18n keys

**File**: `frontend/src/i18n/locales/pl.json`, `frontend/src/i18n/locales/en.json`

**Intent**: Add the `variant.*` keys above in both languages.

**Contract**: new object `variant` with `stock`, `stockOnly`, `substitute`, `supplier`. `optionKind.*` stays (used as the fallback and by the drafter-related texts).

#### 3. Edit-offer selector

**File**: `frontend/src/components/ReplyDraftSection.tsx` (`EditForm`, ~`:459-527`), `ReplyDraftSection.test.tsx`

**Intent**: Name each choice with `variantName` so the selector matches the Warianty step and is unambiguous.

**Contract**: `choices` carry `lines`: the current-offer fallback entry uses `offer.lines`. `draft.optionLabel` becomes `{{name}} · {{value}}` in both locales. Update the tests that assert option texts.

### Success Criteria:

#### Automated Verification:

- Unit tests for `variantName` cover stock only, stock + substitute, stock + supplier, combined, no own stock, no lines (fallback), in EN: `npm test -- variantName` (from `frontend/`)
- Frontend tests pass: `npm test` (from `frontend/`)
- Type checking passes: `npm run typecheck` (from `frontend/`)
- Lint passes: `npm run lint` (from `frontend/`)

#### Manual Verification:

- In the kitchen sink, the edit-offer selector (Akceptacja, "Edit offer") lists readable names in PL, e.g. "Stan + zamiennik ABC-110 · …"

**Implementation Note**: After automated verification passes, pause for manual confirmation before the next phase.

---

## Phase 2: Comparison table in the Warianty step

### Overview

Replace the cards with the comparison table and per-variant details. Bring in the deadline difference and the readable names.

### Changes Required:

#### 1. VariantComparison component

**File**: `frontend/src/components/VariantComparison.tsx` (new)

**Intent**: Render the variants side by side. Rows are attributes and columns are variants. The recommended variant comes first, labelled and outlined. Below the table, each variant has a `<details>` with its lines, cost and all signals.

**Contract**: props `{ recommendation: RecommendationView; expectedDeadline: string | null }`. Column order: when `status === 'completed'` and `choice` matches an option, that option comes first, then the rest in build order; otherwise build order with no highlight. Table semantics: `<table>` built from `@/components/ui/table`, with a `<caption>` (`variants.caption`, "Porównanie wariantów"). The header row is `<th scope="col">` with the `variantName`. The recommended header also shows a `Badge` "Rekomendowany" and the column gets an accent outline/background via token classes (not colour alone). Each row header is `<th scope="row">`. Rows:
- **Pokrycie**: `common.coverage` (covered/requested);
- **Termin**: `formatDate(fulfilled_on)` + relation: `variants.deadline.late` ("{{count}} dni po terminie", plural forms), `.early` ("{{count}} dni przed terminem"), `.onDay` ("w dniu terminu"), `.none` ("brak terminu");
- **Wartość**: `formatPln(value)`;
- **Marża**: `formatPercent(margin_percent)`;
- **Ryzyka**: the `risk` signals' labels as a list, or `variants.noRisks` ("brak");
- **Pewność**: `recommendation.band.<band>`.

Details: one `<details>` per variant in column order. The summary is the variant name. The body shows the lines (existing `recommendation.line` text), cost, and the signal lists (reuse `SignalLists`, cited marks only for the chosen variant). The recommended variant's details are open by default.

#### 2. RecommendationSection uses it

**File**: `frontend/src/components/RecommendationSection.tsx`

**Intent**: Keep banners, the rerun flow, the blocked/stale/not-run states and the "recommended at" meta. Replace the chosen card and the "other options" list with: the recommended variant's name, "Dlaczego ta rekomendacja?" + justification (once), then `VariantComparison`. Remove `OptionCard`. Move `SignalLists` and the line text where `VariantComparison` can use them.

**Contract**: new prop `expectedDeadline: string | null`. `recommendation.noOptions` is still shown when there are no options (no table). Unused keys (`recommendation.chosen`, `.options`, `.otherOptions`) are removed from both locales if nothing else uses them.

#### 3. AnalysisPanel passes the deadline

**File**: `frontend/src/components/AnalysisPanel.tsx` (~`:802`)

**Intent**: Pass `analysis.fields.deadline` as `expectedDeadline`.

**Contract**: one prop added. No other change to step logic.

#### 4. Legacy CSS cleanup

**File**: `frontend/src/styles/legacy.css`

**Intent**: Delete rules whose last user was the removed card markup (e.g. `.recommendation__chosen`, `.recommendation__band*`, `.metrics__list` if unused elsewhere, `.recommendation__why`). Grep each class across `frontend/src` first. A class built dynamically counts as used.

**Contract**: no new legacy rules. The new component uses token utilities only.

#### 5. i18n and tests

**File**: `pl.json`, `en.json`, `frontend/src/components/RecommendationSection.test.tsx`, `frontend/src/components/VariantComparison.test.tsx` (new), `frontend/src/test/recommendationFixtures.ts` (extend if needed), `AnalysisPanel.test.tsx` (if it asserts card texts)

**Intent**: Add the `variants.*` keys. Rewrite tests against the table using roles: `table` named by caption, `columnheader` names, `rowheader`, `cell`.

**Contract**: tests cover:
- the recommended column is first and carries "Recommended";
- a failed recommendation has build order and no "Recommended";
- the deadline relation for late / early / on day / no deadline;
- the risks cell lists only risk signals, or "none";
- one details per variant, the recommended one open, with cited marks;
- two substitutes get two distinct column names;
- the existing blocked/stale/rerun tests still pass.

### Success Criteria:

#### Automated Verification:

- New and rewritten tests pass: `npm test -- RecommendationSection VariantComparison` (from `frontend/`)
- Frontend tests pass: `npm test` (from `frontend/`)
- Type checking passes: `npm run typecheck` (from `frontend/`)
- Lint passes: `npm run lint` (from `frontend/`)
- No literal colours in views: the AGENTS.md scan, with `VariantComparison` added to its file list, prints nothing

#### Manual Verification:

- Kitchen sink at 1440 px, PL, light and dark: the Warianty step shows the table with the recommended column first, labelled and outlined, and the justification above it. Each piece of information appears once.

**Implementation Note**: After automated verification passes, pause for manual confirmation before the next phase.

---

## Phase 3: Narrow screen and kitchen sink

### Overview

Make the table honest at 375 px, add kitchen-sink states, and run the final checks.

### Changes Required:

#### 1. Scroll region and overflow signal

**File**: `frontend/src/components/VariantComparison.tsx`

**Intent**: Keep the attribute column visible while the variant columns scroll, and announce that more columns exist when they do not fit.

**Contract**:
- The scroll container is a focusable region: `tabIndex={0}`, `role="region"`, `aria-labelledby` the caption or `aria-label` `variants.scrollRegion`, and a visible focus ring with `focus-visible:ring-ring`.
- The row-header column is `sticky left-0` with a `bg-card` (or row) background so content does not show through.
- While `scrollWidth > clientWidth`, a visible text `variants.scrollHint` ("Wariantów: {{count}} — przewiń w bok, aby zobaczyć wszystkie") renders above the table and is referenced by `aria-describedby`. It is hidden when everything fits.
- Variant columns get a sensible `min-w-*` token width so values do not wrap into unreadable stacks.
- The page itself never scrolls horizontally.

#### 2. Kitchen-sink states

**File**: `frontend/src/kitchen-sink.tsx`, `frontend/src/test/recommendationFixtures.ts`

**Intent**: Show the comparison states for visual checks.

**Contract**: add panel cases/cells for:
- many variants (≥4, incl. two substitutes and a combined one), so the 375 px signal shows;
- no customer deadline;
- a late recommended variant.

`variantsFailed` (no highlight, build order) already exists and must still render. Not added to `build.rollupOptions.input`.

#### 3. AGENTS.md scan list

**File**: `AGENTS.md`

**Intent**: Add `VariantComparison` to the colour-scan file list (and `variantName.ts` if it holds class names; otherwise not).

**Contract**: the brace list in the grep command gains `VariantComparison`.

### Success Criteria:

#### Automated Verification:

- Frontend tests pass: `npm test` (from `frontend/`)
- Type checking passes: `npm run typecheck` (from `frontend/`)
- Lint passes: `npm run lint` (from `frontend/`)
- Build passes: `npm run build` (from `frontend/`)
- The AGENTS.md colour scan (updated list) prints nothing

#### Manual Verification:

- Kitchen sink at 375 px (DOM/ARIA first): `document.documentElement.scrollWidth <= innerWidth`; the scroll region is focusable and scrolls with arrow keys; the scroll hint is visible in the many-variants case and absent when all columns fit; the attribute column stays in view while scrolling
- Kitchen sink at 1440 and 375 px, PL/EN, light/dark: the recommended label and outline are visible, the focus ring is visible, and dark-mode contrast of the sticky column background is fine (one final screenshot allowed)
- In the real app with the backend, an exception inquiry's Warianty step shows the table with readable names and the deadline relation matching the parsed deadline

**Implementation Note**: After automated verification passes, pause for manual confirmation.

---

## Testing Strategy

### Unit Tests:

- `variantName`: every line-source combination, no own stock, fallback.
- `VariantComparison`: column order and highlight, deadline relation (late / early / on day / none, plural forms in EN), risks cell, details content and open state, duplicate-kind disambiguation.
- `RecommendationSection`: existing blocked/stale/rerun/error tests kept; result assertions moved to table roles.
- `ReplyDraftSection`: selector option names.

### Manual Testing Steps:

1. Kitchen sink → Warianty step at 1440 px: compare columns, open/close details.
2. Resize to 375 px: confirm the hint, the sticky column, keyboard scrolling and no page scroll.
3. Failed-recommendation case: no "Recommended", build order.
4. Akceptacja → Edit offer: readable names in the selector.

## Performance Considerations

One `ResizeObserver` per comparison table; disconnect on unmount. Variant counts are small (single digits), so no virtualisation is needed.

## Migration Notes

None. Display-only change, no stored data touched (lessons.md JSONB rule does not apply).

## References

- Roadmap: `context/foundation/roadmap.md` (S-13)
- PRD: `context/foundation/prd.md` FR-017, FR-007
- Previous slice: `context/archive/2026-11-16-inquiry-steps/plan.md`
- Narrow-table precedent: `context/archive/2026-11-16-run-inspector-and-system-page/plan.md:331`
- Current cards: `frontend/src/components/RecommendationSection.tsx:120-298`
- Option builder: `backend/app/recommendation/options.py:218-295`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Readable variant names

#### Automated

- [x] 1.1 Unit tests for variantName cover all line combinations and the fallback
- [x] 1.2 Frontend tests pass
- [x] 1.3 Type checking passes
- [x] 1.4 Lint passes

#### Manual

- [x] 1.5 Kitchen-sink edit-offer selector lists readable names in PL

### Phase 2: Comparison table in the Warianty step

#### Automated

- [ ] 2.1 New and rewritten RecommendationSection/VariantComparison tests pass
- [ ] 2.2 Frontend tests pass
- [ ] 2.3 Type checking passes
- [ ] 2.4 Lint passes
- [ ] 2.5 AGENTS.md colour scan with VariantComparison prints nothing

#### Manual

- [ ] 2.6 Kitchen sink at 1440 px PL light/dark: recommended column first, labelled and outlined, each information once

### Phase 3: Narrow screen and kitchen sink

#### Automated

- [ ] 3.1 Frontend tests pass
- [ ] 3.2 Type checking passes
- [ ] 3.3 Lint passes
- [ ] 3.4 Build passes
- [ ] 3.5 AGENTS.md colour scan (updated list) prints nothing

#### Manual

- [ ] 3.6 At 375 px: no page scroll, focusable scroll region, hint shown only on overflow, sticky attribute column
- [ ] 3.7 At 1440 and 375 px PL/EN light/dark: highlight, focus ring and sticky-column contrast fine
- [ ] 3.8 Real app with backend: Warianty table with readable names and correct deadline relation
