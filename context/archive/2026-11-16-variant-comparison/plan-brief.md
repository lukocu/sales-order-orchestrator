# Variant comparison side by side — Plan Brief

> Full plan: `context/changes/variant-comparison/plan.md`

## What & Why

The salesperson compares fulfilment variants side by side: coverage, date against the expected deadline, value, margin, risks and confidence. Each variant has a readable name ("Stan + zamiennik ABC-110"), and the recommended one is highlighted. This is roadmap S-13 (FR-017, FR-007, US-01, 375 px NFR). Today the variants are stacked cards named only by their kind, so two substitutes carry the same name.

## Starting Point

`RecommendationSection` renders the chosen option as a card with the justification, and the other options as a list of cards (`<dl>` per option). Names come from `optionKind.*`. The edit-offer selector in `ReplyDraftSection` uses the same ambiguous names. The customer's deadline is in `analysis.fields.deadline`, while options only carry `meets_deadline`.

## Desired End State

The Warianty step shows the recommended variant's name and justification, then a table. Columns are variants (the recommended one first, labelled "Rekomendowany" and outlined) and rows are the six FR-017 attributes. Below the table, one `<details>` per variant holds its lines, cost and all signals. The deadline row reads e.g. "12.12.2026 · 3 dni po terminie". At 375 px the attribute column sticks, the table scrolls inside a focusable region, and a visible hint says how many variants there are and to scroll. The page never scrolls sideways. The selector at Edit offer uses the same names.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Layout at 375 px | Columns = variants; sticky attribute column; scroll region with visible "przewiń w bok" hint on overflow | True side by side on every width, reusing `Table` and the S-11 precedent, and nothing is hidden without a signal. |
| Table vs details | Six attributes in the table; lines, cost, all signals in `<details>` per variant; cards removed | Table stays scannable and each fact appears once (S-12 rule). |
| Deadline | Date + difference in days from `fields.deadline` ("brak terminu" when none) | Shows the size of the delay, not just yes/no. |
| Readable names | One `variantName({kind, lines})` used in Warianty and in the edit-offer selector | Same name in every step; two substitutes/suppliers become distinguishable. |
| Order / highlight | Recommended first with label + outline; others in build order; failed recommendation → build order, no highlight | Visible at 375 px without scrolling, and not signalled by colour alone. |
| Name source | Derived from `lines` (source, product_code, supplier), not by parsing `option.id` | Ids are a backend detail; stored data untouched. |

## Scope

**In scope:**
- `variantName` helper + i18n
- `VariantComparison` component
- `RecommendationSection` rework and the `expectedDeadline` prop from `AnalysisPanel`
- edit-offer selector names
- legacy CSS cleanup
- kitchen-sink states
- AGENTS.md scan list
- tests

**Out of scope:**
- backend/API/JSONB changes
- user sorting/filtering
- a card layout on mobile
- changes to Akceptacja/Odpowiedź beyond selector names
- orchestration findings and run inspector

## Architecture / Approach

The pure helper `variantName` is paired with the presentational `VariantComparison(recommendation, expectedDeadline)`. `RecommendationSection` keeps its states, rerun flow and banners, and delegates the result body. Overflow is detected with a `ResizeObserver` (`scrollWidth > clientWidth`) and drives the hint. Everything uses token classes and `t()`.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Readable variant names | `variantName` + selector in Edit offer | Selector tests assert old texts |
| 2. Comparison table | Table + details replace cards; deadline in days | Rewriting text-based tests to table roles |
| 3. Narrow screen and kitchen sink | Sticky column, focusable scroll region, overflow hint, states, 375 px check | jsdom has no layout, so the overflow hint is verified in the browser |

**Prerequisites:** S-12 merged (done, main f651165).
**Estimated effort:** about one session across 3 small frontend phases.

## Open Risks & Assumptions

- The day difference is computed on the frontend from the current `fields.deadline`. If the fields changed after the recommendation, the existing stale notice covers the mismatch with `meets_deadline`.
- Many variants (substitutes × suppliers) make a wide table. This is acceptable with the scroll hint, and there is no pagination.

## Success Criteria (Summary)

- The salesperson sees all variants side by side under distinct readable names, with the recommended one first and clearly marked.
- At 375 px there is no page scroll, and hidden columns are announced by a visible hint in a keyboard-scrollable region.
- Tests, typecheck, lint, build and the colour scan pass.
