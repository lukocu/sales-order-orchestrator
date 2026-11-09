# Evidence brief: rules guarded in the code

You are one of the sub-agents distilling a domain. Your source is **the
code's guards** — every place that stops, rejects or constrains a business
operation. Write `context/domain/evidence/3-code-rules.md` (or the
`3-code-rules-<group>.md` path you were given when the work is split) and
return at most 15 lines.

Question: **which business rules does the code actually guard, where, and
how strictly?**

Read first: `context/domain/evidence/0-sources.md` for the code scope, the
stack and the layer patterns; when you were given a group, search for guards inside it, but you may read
shared schema and migrations outside it to settle a rule you cite. Do
not read the domain documents or `0-documents.md`: inventory what the code
enforces, not what someone says it should. The main agent matches your
guards to the documented rules afterwards. Skip the paths listed as
excluded.

## 1. Find the guards

Search every layer, by the conventions of the stack:

- **database** — `NOT NULL`, `UNIQUE`, `CHECK`, foreign keys, exclusion
  constraints, triggers, row-level policies, enum types, function bodies that
  raise errors;
- **domain and application code** — preconditions that throw or return an
  error, state-transition checks, authorization checks on business objects,
  explicit domain error types;
- **entry points** — request validation schemas, permission middleware,
  idempotency keys; read paths that filter what a user may see;
- **UI** — disabled buttons, client-side validation, hidden actions,
  confirmation dialogs;
- **transactions** — which multi-step writes run atomically and which do not.

Business guards only: skip input-format checks with no business meaning
(string length of a free-text field), unless they encode a rule (a maximum
number of seats).

## 2. Describe each guarded rule

| rule (in plain words) | guarded at (layer: path:line) | paths covered | strictness | failure handling |

- **Rule** — one sentence, your words, marked as inference.
- **Guarded at** — every place guarding the same rule; a rule guarded in
  three layers is three rows grouped together.
- **Paths covered** — the write paths (and, for visibility rules, the read
  paths) the guard sits on, against those you found that the rule
  constrains.
- **Strictness**:
  - _hard (data)_ — the data store rejects a violation (constraint, policy,
    trigger) whoever writes;
  - _hard (app)_ — every writer found in this code goes through the check,
    but the data store would accept a violating write;
  - _soft_ — checked on some paths, others can write or read without it;
  - _client-only_ — only the UI checks it; any direct call bypasses it. Note
    when the state itself lives on the client by design (browser storage) —
    there, a client check may be the right place.
- **Failure handling** — one of: _named error_ (stops with a domain error),
  _generic error_, _logs and continues_, _swallowed silently_ (no log, the
  operation goes on), _silently corrects_ (rewrites the data). The last three
  are findings.

For a _soft_ rule, show one path that bypasses the check, or say that you
could not establish whether one exists. When you find a writer that actively
does the opposite of a guard elsewhere (resets, overrides, back doors),
record it next to that rule.

## 3. Atomicity

For each multi-step business operation you met (create with children, move
money, change state and notify), whether its writes share one transaction,
with citations. Partial writes on failure are a finding.

## 4. Scheduled and asynchronous work

For each rule that depends on something running later — a cleanup, an
expiry, a retry, a reminder — find the trigger (schedule configuration,
queue binding, timer) and confirm it reaches the handler. A handler with no
trigger, or a trigger with no handler, is a finding.

## Evidence file

```markdown
# Evidence: rules guarded in the code

<scope or group, layers searched, patterns used, areas not covered>

## Guarded rules <!-- table above, grouped by business concept -->

## Soft and client-only rules

## Writers that work against a guard

## Failure handling

## Atomicity

## Scheduled and asynchronous work

## Unknowns
```

Name the commands you ran in one short list at the end.
