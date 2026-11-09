# Research document format

Read when writing or checking research.md. Populate metadata from observed values;
if unavailable, mark it unknown rather than inventing it. Use `status: complete`
only when the agreed scope is answered; use `status: partial` for material missing
evidence and explain the gap. Keep sections concise; mark irrelevant history or
related research as not applicable instead of initiating new discovery to fill them.

```markdown
---
date: [Current date and time with timezone in ISO format]
researcher: [Researcher name]
git_commit: [Current commit hash]
branch: [Current branch name]
repository: [Repository name]
topic: "[User's Question/Topic]"
tags: [research, codebase, relevant-component-names]
status: complete
last_updated: [Current date in YYYY-MM-DD format]
last_updated_by: [Researcher name]
---

# Research: [User's Question/Topic]

**Date**: [Current date and time with timezone gathered before writing]
**Researcher**: [Researcher name]
**Git Commit**: [Current commit hash gathered before writing]
**Branch**: [Current branch name gathered before writing]
**Repository**: [Repository name]

## Research Question

[Original user query]

## Summary

[High-level findings answering the user's question]

## Detailed Findings

### [Component/Area 1]

- Finding with reference ([file.ext:line](link))
- Connection to other components
- Implementation details

### [Component/Area 2]

...

## Code References

- `path/to/file.py:123` - Description of what's there
- `another/file.ts:45-67` - Description of the code block

## Architecture Insights

[Patterns, conventions, and design decisions discovered]

## Historical Context (from prior changes)

[Relevant insights from `context/changes/**/` and `context/archive/**/` with references]

- `context/changes/<other-change>/plan.md` - Historical decision about X
- `context/archive/YYYY-MM-DD-<other-change>/research.md` - Past exploration of Y

## Related Research

[Links to other research artifacts under `context/changes/**/research.md` or `context/archive/**/research.md`]

## Open Questions

[Any areas that need further investigation]
```

## Bounded assertions (required before save)

Every quantitative or universal sentence in Summary, Detailed Findings, Historical
Context, and any structured companion file must carry all three:

1. **Condition** — when the claim holds (inputs, branch, status sequence, override).
2. **Quantifier** — exact count, exact set, or “this inspected path only”.
3. **Source** — `path:line` (or commit permalink if bytes match that commit).

Do not promote a positive list into an exclusive set (`just {500, 503}`, “only those
statuses”) unless the source uses exclusive wording. Do not collapse “stops the
current iteration” into “returns on the first attempt”.

## Historical claims

Score each historical sentence separately as supported / contradicted / partial, with
the exception named. A stale count does not license calling the whole note false.

## Prose vs JSON checklist

When the task asks for JSON or a facts table, complete this pass **before** writing
either file and again on the persisted bytes:

- [ ] Each JSON number and boolean has a matching prose sentence with the same
      condition and units.
- [ ] Each prose number/boolean has a JSON leaf (or an explicit “prose-only” note).
- [ ] No summary uses a broader quantifier than the JSON leaf it describes.
- [ ] `node <loaded-skill-dir>/scripts/prose-json-check.mjs <research.md> <facts.json>`
      when Node is available (leaf presence only; not a substitute for the
      checklist).
