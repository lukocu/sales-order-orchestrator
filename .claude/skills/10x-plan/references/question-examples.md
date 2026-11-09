## Example AskUserQuestion Probing by Feature Type

### Example 1: Software / UI Feature — MEDIUM complexity (e.g., Pagination)

Mixed: `Loading UX` is `[S]` (UI behavior — solution detail); `Scale` is `[D]` (problem boundary — how big is the dataset). With a frame brief, ask only `Loading UX`; the scale should already be in the Reframed (or Confirmed) Problem Statement.

AskUserQuestion with questions:

- question: "What should the user see while new items load?"
  header: "Loading UX"
  options:
  - label: "⭐ Recommended: Skeleton screens (Recommended)"
    description: "Placeholder shapes matching item layout. · Strength: Perceived performance is 30-40% better — matches existing LoadingSkeleton component pattern. · Tradeoff: Requires a skeleton variant per item type; breaks if layout changes."
  - label: "Inline spinner"
    description: "Small spinner below existing content. · Strength: User keeps seeing current items, minimal UI work. · Tradeoff: Feels slower than skeleton — users see a generic spinner instead of content shape."
  - label: "Full-page spinner"
    description: "Replace content with spinner. · Strength: Simplest to implement — one component, no layout concerns. · Tradeoff: Blocks all interaction; feels broken on slow connections."
    multiSelect: false
- question: "How many items should this handle gracefully?"
  header: "Scale"
  options:
  - label: "⭐ Recommended: Hundreds (Recommended)"
    description: "Standard offset pagination. · Strength: Simple, well-understood, works with existing SQL queries. · Tradeoff: Breaks down past ~5k items — acceptable given current data volumes."
  - label: "Thousands"
    description: "Cursor-based pagination + virtual scrolling. · Strength: Handles growth without performance cliff. · Tradeoff: 2-3x more implementation work; changes API contract."
  - label: "Tens of thousands"
    description: "Server-side filtering + virtual list + search. · Strength: Scales indefinitely. · Tradeoff: Significant complexity; requires search index and new API design."
    multiSelect: false

### Example 2: Content / Education — HIGH complexity (e.g., Course Module Design)

Mixed: `Outcome` is `[D]` (defines what success looks like — pure problem framing); `Levels` is `[S]` (audience-handling strategy — how to structure delivery). With a frame brief, ask only `Levels`; the outcome should be settled.

AskUserQuestion with questions:

- question: "What should the learner be able to DO after this module — not just know?"
  header: "Outcome"
  options:
  - label: "⭐ Recommended: Working prototype (Recommended)"
    description: "Learner produces a functional artifact using the techniques taught. · Strength: Forces genuine skill transfer — the artifact proves competence. Matches the 'Innovate' lesson format from 10xDevs3. · Tradeoff: Requires well-designed starter templates and clear acceptance criteria; takes 2-3x longer to prep."
  - label: "Complete a guided exercise"
    description: "Step-by-step walkthrough with expected output. · Strength: Low barrier — everyone finishes, builds confidence. · Tradeoff: May produce 'tutorial zombies' who can follow but not apply independently."
  - label: "Pass a knowledge check"
    description: "Quiz or code review proving conceptual understanding. · Strength: Fast to create, easy to grade at scale. · Tradeoff: Tests recognition not production — learner may understand but not be able to execute."
    multiSelect: false
- question: "How should this module handle different skill levels in the audience?"
  header: "Levels"
  options:
  - label: "⭐ Recommended: Layered depth (Recommended)"
    description: "Core path everyone follows + optional deep-dive sections. · Strength: Everyone gets value; advanced learners self-select into harder material. · Tradeoff: More content to maintain; risk of 'optional' sections being ignored."
  - label: "Single track, advanced"
    description: "One path targeting experienced devs. · Strength: Deep content, no hand-holding, respects expert time. · Tradeoff: Alienates beginners — they'll drop off or flood support channels."
  - label: "Separate beginner/advanced tracks"
    description: "Two parallel paths diverging early. · Strength: Each audience gets perfectly targeted content. · Tradeoff: 2x production cost; splitting a small cohort may hurt community dynamics."
    multiSelect: false

### Example 3: Strategy / Process — MEDIUM complexity (e.g., Newsletter Workflow)

`Bottleneck` is `[D]` — pure problem framing (which problem to solve). This is exactly the kind of question a frame exists to settle. With a frame brief, skip this entirely; the leading hypothesis is the bottleneck.

AskUserQuestion with questions:

- question: "What's the primary bottleneck in the current newsletter pipeline?"
  header: "Bottleneck"
  options:
  - label: "⭐ Recommended: Slow curation (Recommended)"
    description: "Finding and evaluating links is the slow step. · Strength: Directly targets time-to-publish — automating curation yields the biggest time savings based on current pipeline timings. · Tradeoff: Automated curation risks losing the personal editorial voice that subscribers value."
  - label: "Writing the commentary"
    description: "Links are ready but writing around them is slow. · Strength: AI-assisted drafting can cut this in half. · Tradeoff: Heavy AI drafting can make the newsletter feel generic — needs careful voice calibration."
  - label: "Distribution and scheduling"
    description: "Content is ready but publishing is manual. · Strength: Easiest to automate — clear inputs and outputs. · Tradeoff: Lowest impact if curation or writing is still the bottleneck."
    multiSelect: false

**Note**: Questions focus on **WHAT should happen** (requirements, behavior, outcomes) — NOT **HOW to implement it** (code patterns, specific tools). The `⭐ Recommended` pick is grounded in research and context — the user always has the final say.

## Undefined terms in the request

Ranking, selection and state words carry a decision the request never makes. Run this pass in Step 1.1, before choosing interview questions.

| Term shape        | Examples                                          | Build the smallest case by                                                                                   |
| ----------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Ordered selection | "top 5", "latest", "first", "winner", "best"      | placing equal comparison values across the cutoff — the Nth and the N+1th tie exactly                        |
| Counted set       | "all", "how many", "per user", "duplicate"        | varying the identity rule — are two rows sharing an email one item or two, and does a soft-deleted row count |
| State threshold   | "active", "overdue", "until the end of the month" | varying inclusivity and the governing clock — exactly at the boundary instant, in whose timezone             |

**Keep a working note, one line per term, before looking up the implementation**: the term, the case, and what the user would see differently under each reading. Then read the code and add its answer as one more line. A tiebreak the code performs by id, insertion order or array position is not a decision anyone made, so it never closes the note. The note is scaffolding for the interview — it is not a plan section and nothing carries it into the plan.

**Phrasing the question.** Put the concrete data in it, never the category name. When the code already implements one reading, mark that option `(current behaviour)` inside its label so the user sees a choice rather than a given. That option takes the `⭐ Recommended` star and first position only when its outcome is one the user would defend without mentioning the implementation; otherwise star the reading you would argue for and list the current behaviour below it.

AskUserQuestion with questions:

- question: "Orders 4 and 5 share the same `created_at` to the second. Which one does 'the latest order' mean?"
  header: "Tiebreak"
  options:
  - label: "⭐ Recommended: Higher id wins (current behaviour) (Recommended)"
    description: "On equal timestamps the larger primary key is selected. · Strength: Deterministic and already what `getLatestOrder` returns, so no existing caller changes behaviour — and for an auto-increment key the higher id really is the later insert. · Tradeoff: Silently wrong for backfilled or imported rows, whose ids do not follow insertion time."
  - label: "Most recently updated wins"
    description: "Break the tie on `updated_at`, falling back to id when that is equal too. · Strength: Matches what users mean by 'latest' when they have just edited one of the two orders. · Tradeoff: An unrelated status edit reorders the pair, so the answer moves without a new order being placed."
  - label: "Return both and let the caller decide"
    description: "Surface the tie instead of resolving it. · Strength: No hidden rule — the ambiguity reaches whoever has the context to settle it. · Tradeoff: Every call site now handles a list where it expected one order; the dashboard and the invoice job both need a branch."
    multiSelect: false

**Where the answer lands.** A term the user settles becomes a named test or an explicit success criterion in the plan; a term the user declines to handle goes under "What We're NOT Doing", so a reviewer sees a decision rather than an omission. Neither gets a section of its own.
