# Plan and brief artifact templates

Read when drafting or validating the plan and brief, after structure approval.
Use the current agreed decisions; these templates do not authorize implementation
or override the mode-aware persistence route. Required sections and canonical
Progress remain the same when the documents are presented in the conversation.

## Full plan

```markdown
# [Feature/Task Name] Implementation Plan

## Overview

[Brief description of what we're implementing and why]

## Current State Analysis

[What exists now, what's missing, key constraints discovered]

## Desired End State

[A Specification of the desired end state after this plan is complete, and how to verify it]

### Key Discoveries:

- [Important finding with file:line reference]
- [Pattern to follow]
- [Constraint to work within]

## What We're NOT Doing

[Explicitly list out-of-scope items to prevent scope creep]

## Implementation Approach

[High-level strategy and reasoning]

## Critical Implementation Details

This section captures **constraints, gotchas, and ordering requirements that the implementer needs to know before they touch the code** — facts the LLM determines during Research & Discovery (Step 2) that aren't visible from the file paths alone.

This is NOT a place to pre-decide implementation. Default: **omit** the entire section. Include a heading below ONLY when something genuinely surprising or load-bearing applies — and write 1-3 sentences, not bullet templates.

- **Timing & lifecycle** — include only if there's a non-obvious ordering, race, or lifecycle hook the implementer would otherwise miss.
- **User experience spec** — include only when user-visible behavior has constraints not derivable from the user requirements (e.g. specific focus management, scroll preservation).
- **Performance constraints** — include only when there's a real performance budget or known hotspot; skip generic "use memoization" advice.
- **State sequencing** — include only when the order of state changes matters and the obvious order is wrong.
- **Debug & observability** — include only when there's a specific verification method or instrumentation need beyond standard logging.

If none apply, omit the section entirely. A plan without it is not incomplete; a plan that fills it with templated bullets is bloated.

## Phase 1: [Descriptive Name]

### Overview

[What this phase accomplishes]

### Changes Required:

#### 1. [Component/File Group]

**File**: `path/to/file.ext`

**Intent**: [1-2 sentences naming what this change does and why. The implementer will write the actual code.]

**Contract**: [The interface, signature, schema field, route, file-structure delta, or invariant the change touches. For pure-prose edits, name the section or heading affected.

A code snippet appears here ONLY when the change is non-obvious — a tricky regex, an unusual API call, a counterintuitive ordering, a workaround for a known bug, or a signature contract that other parts of the plan depend on. For routine edits (add a field, wire a handler, follow an existing pattern), describe the contract and stop. Default: no snippet.]

### Success Criteria:

#### Automated Verification:

- Migration applies cleanly: `make migrate`
- Unit tests pass: `make test-component`
- Type checking passes: `npm run typecheck`
- Linting passes: `make lint`
- Integration tests pass: `make test-integration`

#### Manual Verification:

- Feature works as expected when tested via UI
- Performance is acceptable under load
- Edge case handling verified manually
- No regressions in related features

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase. Phase blocks use plain bullets — the corresponding `- [ ]` checkboxes for these items live in the `## Progress` section at the bottom of the plan.

---

## Phase 2: [Descriptive Name]

[Similar structure with both automated and manual success criteria...]

---

## Testing Strategy

### Unit Tests:

- [What to test]
- [Key edge cases]

### Integration Tests:

- [End-to-end scenarios]

### Manual Testing Steps:

1. [Specific step to verify feature]
2. [Another verification step]
3. [Edge case to test manually]

## Performance Considerations

[Any performance implications or optimizations needed]

## Migration Notes

[If applicable, how to handle existing data/systems]

## References

- Related research: `context/changes/<change-id>/research.md`
- Similar implementation: `[file:line]`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: <Phase 1 name>

#### Automated

- [ ] 1.1 <Automated Verification item 1 from Phase 1>
- [ ] 1.2 <Automated Verification item 2 from Phase 1>

#### Manual

- [ ] 1.3 <Manual Verification item 1 from Phase 1>

### Phase 2: <Phase 2 name>

#### Automated

- [ ] 2.1 <…>
```

## Brief

```markdown
# [Feature/Task Name] — Plan Brief

> Full plan: `context/changes/<change-id>/plan.md`
> Frame brief: `context/changes/<change-id>/frame.md` (if present — omit line otherwise)
> Research: `context/changes/<change-id>/research.md` (if present — omit line otherwise)

## What & Why

[2-3 sentences: what we're building/doing and the motivation behind it. If a frame brief was the input, lift the Reframed (or Confirmed) Problem Statement here verbatim — that is the "why" in its sharpest form.]

## Starting Point

[1-2 sentences: what exists today that this plan builds on or changes. Ground the reader in the current state so they understand the delta. If a frame investigated this, summarize from its Hypothesis Investigation rather than re-stating.]

## Desired End State

[2-3 sentences: what the world looks like when this plan is done. Describe the concrete, user-visible outcome — not metrics, but the experience or capability that now exists.]

## Key Decisions Made

When a frame brief or research doc was the input, mark the **Source** column to show where the decision came from. This lets readers see the lineage: what was settled upstream vs decided in this planning session.

| Decision        | Choice            | Why (1 sentence) | Source                  |
| --------------- | ----------------- | ---------------- | ----------------------- |
| [Decision area] | [What was chosen] | [Core rationale] | Frame / Research / Plan |
| [Decision area] | [Choice]          | [Rationale]      | Frame / Research / Plan |
| ...             | ...               | ...              | ...                     |

(Omit the `Source` column if no upstream artifacts were provided — every row would be `Plan`.)

## Scope

**In scope:** [Bullet list of what's included]

**Out of scope:** [Bullet list of what's explicitly excluded]

## Architecture / Approach

[1 short paragraph or a simple diagram describing the high-level approach.
For software: key components, data flow, integration points.
For non-software: structure, workflow, key dependencies.]

## Phases at a Glance

| Phase     | What it delivers       | Key risk                  |
| --------- | ---------------------- | ------------------------- |
| 1. [Name] | [One-line deliverable] | [Primary risk or concern] |
| 2. [Name] | [One-line deliverable] | [Primary risk]            |
| ...       | ...                    | ...                       |

**Prerequisites:** [What must be true before starting — dependencies, access, prior work]
**Estimated effort:** [Rough size: e.g., "~2-3 sessions across 3 phases" or "8 weeks, 2-person team"]

## Open Risks & Assumptions

- [Risk or assumption that could change the plan]
- [Another one]

## Success Criteria (Summary)

[2-3 bullet points: how we know the plan succeeded, from the user's perspective]
```
