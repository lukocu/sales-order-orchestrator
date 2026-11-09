# The report — `context/domain/domain-distillation.md`

Written by the main agent from the inventory and the evidence files. The
evidence holds vocabulary and guards; the report crosses them. Its value is
where the two sides disagree: a term the business uses and the code never
names, a rule the documents state and nothing guards, one word meaning two
things.

Do not generate new data beyond the targeted checks below, and do not copy
the evidence tables whole.

## Crossing the evidence

1. **Documents first.** Where the documents conflict, the newest statement
   is the model the code is compared with; superseded statements go to the
   short _Stale documents_ list, not to the drift table.
2. **Terms.** Match each documented term to a code concept (exact name,
   variant, or clear synonym). Unmatched: a targeted search (batched per
   layer, scope cited). Still unmatched → **missing in code**. Code concepts
   with no documented term → _code-only_, each marked _searched in docs_ or
   _not in the docs sample_ — a thin sample is not evidence of a gap.
   Findings resting only on code comments are weaker than identifiers; say
   so where it decides a match.
3. **Rules.** Match each documented rule to the guards. Status:
   - **enforced** — guarded _hard (data)_ or _hard (app)_ on every path the
     rule constrains (writes, and reads for visibility rules). For _hard
     (app)_, put the missing data-store guard in the gap column;
   - **declared** — guarded _soft_ or _client-only_, or only some of its
     conditions, or named in code (a type, a comment, a test) without
     stopping a violation. Client-only on state that lives on the client by
     design is noted as such in the gap column;
   - **ignored** — no guard after a targeted search; cite the scope;
   - **contradicted** — some code actively does the opposite (an override,
     a reset, a back door). Every contradicted rule also gets a drift row.
     Guards with no documented rule → _code-only rules_: often business
     knowledge nobody wrote down.
4. **Meanings.** Merge the multiple-meaning findings from both language
   agents. A word with two meanings is a likely boundary between two
   contexts; name both contexts.

## Classification and ranking

- **Subdomains.** Group the concepts into subdomains. Classify each as
  **Core** (the reason the product exists — what the product goals depend
  on), **Supporting** (needed and specific to this product, but not where it
  wins) or **Generic** (solved the same way everywhere: sign-in, payments
  processing, e-mail, file storage — a library or a vendor would do).
  Justify each with a product-goal quote, or say the goals are missing or
  change-only and judge from the product description and usage. More than
  one Core subdomain is allowed.
- **Candidates.** Two kinds are ranked together:
  - _aggregate candidates_ — a concept with identity, a lifecycle and at
    least one invariant binding several of its parts or children. Implicit
    concepts (no type of their own) qualify and are often the most valuable;
  - _policies_ — product-wide rules (privacy, access, retention, limits)
    that are ignored or contradicted;
  - _undocumented exposures_ — a code-only rule or its absence that exposes
    data, money or access (an endpoint answering for any user without a
    session). Status **undocumented**; it ranks with _ignored_.
- **Ranking.** Order by status first, then by subdomain:
  contradicted > ignored > declared > enforced, and within a status Core >
  Supporting > Generic; break ties by how spread the guards are across
  layers. A lower-placed item may move up — to #1 as well — only with a
  one-line written reason (blast radius, data loss, exposure); for #1 that
  reason opens the #1 paragraph. Name **#1** with a three-line reason. Ranking is the end: no design, no plan, no code.

## Making it operational

The report is read once; its findings are used for months. Five rules make
them usable after the first read.

1. **Stable IDs.** Number every row that someone may act on: terms `T-01`,
   context boundaries `B-01`, invariants and policies `R-01`, drift `D-01`,
   questions `Q-01`. IDs are ordered by first appearance and never reused
   inside a report. When an archived earlier report (the `previous:` path)
   has IDs, keep the same ID for the same finding (same term, same rule, same drift
   subject) and give new findings the next free number — so a plan, a pull
   request or a ticket can cite `D-03` across runs.
2. **Which side is wrong.** Every drift row says what fixes it:
   - **code** — the documents state a rule still meant to hold, and the
     code breaks it;
   - **docs** — the code reflects a later, deliberate decision (a change
     folder, an ADR, a commit message says so — cite it) and the documents
     were never updated;
   - **decision** — the evidence cannot tell which side is intended, or the
     answer lives outside the repository. Every _decision_ row has a
     question in _Questions_.
     Never mark _docs_ without citing the later decision.
3. **Done when.** Every ranked item gets one observable condition that would
   show it is fixed — a test that would pass, a query that would return
   nothing, a search that would return only one place: "a failed second
   write leaves no order without its lines", "a request with a token of a
   suspended account returns 401", "`rg <package>` matches only the adapter
   directory". A condition, not a design: it says what must be true, never
   how to build it.
4. **Questions with an owner.** Every unknown that a person could settle in
   minutes — a deployed setting, a vendor account option, an intent behind
   a decision — becomes a question with the role that can answer it
   (product owner, operator, whoever owns the infrastructure or the
   integration) and the IDs it unblocks. Unknowns no person can settle stay
   in _Limitations_.
5. **A glossary agents can load.** Write `context/domain/glossary.md` from
   the same data (format below): short, no evidence, meant to be referenced
   from agent instruction files and read before naming anything in code.
   The skill writes it; wiring it into instructions stays with the user.

When an earlier report was archived, add **Changes since the previous
run**: findings closed, findings opened, and status changes (`R-04 declared →
enforced`), matched by ID — or, when the earlier report has no IDs, by
subject, saying so.

## Structure

```markdown
---
artifact: domain-distillation
created: <YYYY-MM-DD>
repo_root: <path>
code_scope: <path>
head: <short sha>
dirty: <paths | none>
path_alias: <optional>
documents: <n requirements, n narrative (n read), n reference, n engineering | README only | none>
previous: <context/archive/<stamp>-domain-distillation/domain-distillation.md | none>
evidence: context/domain/evidence/
glossary: context/domain/glossary.md
---

# Domain distillation: <product name>

## Summary

5–8 sentences: what the domain is, the Core, how many Core and Supporting
terms are missing in code, the strongest drift, #1 and why. One more line
with the counts of drift by fix side (code / docs / decision) and of open
questions.

## Changes since the previous run

Only when a previous report exists: closed, opened, status changes.

## Ubiquitous language

One row per term; variants in "other names". Every Core and Supporting
term; Generic and peripheral terms as counts only. Under the table: totals
in the evidence vs in the table, and missing-in-code counts by kind
(entities, states, measures… — _thesis_ terms are listed, not counted).

| id | term | kind | definition (quoted) | source | in code (path:line) or **missing in code** | other names in code |

Code-only concepts in a short list below, each marked _searched in docs_ or
_not in the docs sample_.

## Multiple meanings and context boundaries

| id | word | meaning A (context, source) | meaning B (context, source) | suggested names |

## Subdomains

| subdomain | class | concepts | why (goal quote, or description and usage) |

## Invariants and policies

| id | candidate | invariant (quoted) | source | status | guarded at | gap |

With more than three candidates, one subheading per candidate with its own
table. Code-only rules in a short list at the end.

## Model vs code drift

| id | the documents say (newest) | the code does | evidence (path:line) | consequence | fix: code / docs / decision |

## Stale documents

Superseded statements, each with the newer one that replaced it — the
starting list for documentation edits, together with the _docs_ drift rows.

## Ranking

| # | candidate | kind | subdomain | status | related IDs | reason | done when |
**#1:** <three lines>

## Questions

| id | question | who can answer | unblocks |

## Unknowns and limitations

Documents missing, thin or change-only; the narrative sample; code areas
not searched; rules whose status could not be settled; configuration
outside the repository that no question covers.
```

Write each table with real rows only. A section with nothing to report says
so in one line.

## Glossary — `context/domain/glossary.md`

```markdown
---
artifact: domain-glossary
created: <YYYY-MM-DD>
source: context/domain/domain-distillation.md
---

# Glossary: <product name>

Use these words in code, tests, commits and conversations. When a name in
the code differs from the term, the term wins in new code; renaming old code
is a separate decision.

## <context, when the product has several; otherwise omit the heading>

| term | means | name in code | don't call it |
```

- One row per Core and Supporting term; Generic terms only when the code
  names them inconsistently.
- **means** — one sentence in plain words (not a quote); **name in code** —
  the dominant identifier, or _missing in code_; **don't call it** — the
  other names found in code and conversation that mean the same thing, plus
  the other meanings of an overloaded word with the context they belong to.
- Each context boundary (`B-…`) becomes a heading, so an overloaded word
  appears once per context with its own meaning.
- At most ~60 rows; no citations, no evidence — the report holds them.

## Verification

Before presenting, check the written report once:

- every term in the table has a code location or **missing in code** with
  the scope searched; no row has both;
- every invariant and policy has one of the statuses above (enforced,
  declared, ignored, contradicted, undocumented); every _ignored_
  row cites the scope searched, every _contradicted_ row has a drift row;
- every drift row has a fix side; every _docs_ row cites the later decision;
  every _decision_ row has a question;
- every ranked item has a _done when_ that states a condition, not a design;
- IDs are unique, and every ID cited in the ranking or the questions exists;
- open **every** citation in the drift table and in the #1 reason, plus 5
  random others, and confirm each says what the report claims; fix any that
  do not, and re-check the rows that depend on them — including caveats the
  source states and the row dropped;
- quotes are the sources' words, not paraphrases;
- no section proposes a design, a refactor or code;
- the glossary agrees with the report's term table;
- the frontmatter `head` and `dirty` match the current state.
