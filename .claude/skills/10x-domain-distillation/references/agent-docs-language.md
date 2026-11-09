# Evidence brief: language in the documents

You are one of the sub-agents distilling a domain. Your source is **the
documents** listed in the inventory — not the code. Write
`context/domain/evidence/1-docs-language.md` and return at most 15 lines.

Question: **which words, lifecycles and rules does the business state?**

Read first: `context/domain/evidence/0-sources.md` and
`context/domain/evidence/0-documents.md`. Do not open source code — other
agents cover it, and staying out keeps your findings independent.

## Reading budget

- **Requirements:** read fully.
- **Reference:** read the parts that define business words or rules.
- **Engineering:** read for rules only.
- **Narrative:** read every title. Read in full at most ~20, choosing the
  most recent and those whose titles name business nouns; prefer briefs,
  plans and decisions over research notes and logs. Report the sample —
  which you read, how many you only titled.

## 1. Terms

One row per term; variants go in their own column. For every domain term — a
thing, a role, a state, an operation, an event, a measure, a policy —
record:

- the term exactly as written, and its variants (singular and plural,
  abbreviations, the same idea in another language);
- the definition in the source's own words, quoted, with `path:line`;
- where it appears (the strongest 1–3 citations);
- its kind: _entity_ (identity and a lifecycle), _value_ (defined only by
  its content), _role_, _state_, _operation_, _event_, _measure_, _policy_
  (a product-wide rule or guarantee), _thesis_ (a positioning or strategy
  word with no runtime meaning).

Skip technical vocabulary (database, endpoint, cache) unless the documents use
it as a business word.

## 2. Lifecycles

For each entity with a lifecycle, the states and transitions the documents
describe — who or what moves it, and what must hold first. Quote the
sources. Partial lifecycles are fine; mark the missing transitions.

## 3. Rules

Every statement of something that **must always** or **must never** hold:
"an order ships only when paid", "a booking cannot overlap another booking
of the same room", "a user sees only their own workspace's documents".
Record the rule in the source's words, `path:line`, the terms it binds, and
whether it is about one entity or product-wide (a policy). These are
invariant candidates; do not judge enforcement — you have not seen the code.

## 4. Conflicts and multiple meanings

- **One word, several meanings** in different parts of the product — "order"
  as a purchase in sales and as a picking task in the warehouse. Both
  citations. This marks a boundary between contexts.
- **Conflicting statements** — the same term defined differently, a renamed
  concept, a rule stated and later reversed. Give both citations and mark
  which statement is newer (by date in the document, folder order or git
  history). The synthesis compares the code with the newest statement.

## Evidence file

```markdown
# Evidence: language in the documents

<documents read, the narrative sample, documents skipped and why>

## Terms <!-- term, variants, kind, definition (quoted), source -->

## Lifecycles

## Rules <!-- rule (quoted), binds terms, entity or policy, source -->

## Multiple meanings

## Conflicting statements <!-- older, newer, both cited -->

## Unknowns
```

Name the commands you ran in one short list at the end.
