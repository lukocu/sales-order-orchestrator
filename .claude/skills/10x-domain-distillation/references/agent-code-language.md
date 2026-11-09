# Evidence brief: language in the code

You are one of the sub-agents distilling a domain. Your source is **the
code** — names, not behaviour. Write
`context/domain/evidence/2-code-language.md` and return at most 15 lines.

Question: **which words does the code use for the business, and for what?**

Read first: `context/domain/evidence/0-sources.md` for the code scope, the
stack and the layer patterns. Do not read the domain documents or
`0-documents.md` — not knowing their vocabulary keeps your findings
independent. Use the file listing and `rg`; open files only to confirm what a
search pointed at. Skip the paths listed as excluded.

**Prose inside the code counts as documents.** Comments and docstrings often
quote the product documents, and agent instruction files that describe the
product are listed as documents in the inventory — do not read those.
Harvest identifiers, schema objects, routes and user-facing labels; when a finding rests only on a comment, tag it
`comment` so the synthesis can weigh it.

## 1. Harvest names per layer

Collect business-meaning names, by the conventions of the stack:

- **persistence** — table, collection and column names from schema files and
  migrations; ORM model names; database functions and policies;
- **domain types** — type, class, struct, record, interface and enum names,
  and enum members that name states;
- **operations** — names of services, use cases, commands, handlers and their
  public methods;
- **entry points** — route paths, command names, job and queue names, event
  and message names;
- **UI** — screen and component names, and user-visible labels from
  translation or copy files, in whatever language they are written.

Drop pure technical names (`utils`, `helpers`, `client`, `manager` with no
business noun). Keep the business noun inside a technical name
(`InvoiceRepository` → _invoice_).

## 2. Group into concepts

Group names that clearly refer to one business concept across layers. For
each concept, every name it carries per layer, with one `path:line` each:

| concept | persistence | domain type | operations | entry points | UI | user-facing label (language) |

Then flag:

- **one concept, many names** — the table says `draft`, the type says
  `Proposal`, the UI says "suggestions";
- **one name, many concepts** — `Account` used for a login in one module and
  for a balance in another; show both usages;
- **implicit concepts** — a concept with no type of its own, living only as a
  loose id, a flag or a column group (`batch_id` on many rows, a `status`
  string compared in several places);
- **states** — status fields and enums, the members, and where transitions
  are written (`status = …`, state machine definitions).

## 3. Where business logic lives

For the main concepts, which layer holds their logic: domain type, service,
route handler, UI, database (constraints, triggers, policies). One line each
with citations. A codebase without a domain layer is a finding.

## Evidence file

```markdown
# Evidence: language in the code

<scope, layers covered, search patterns used, areas sampled rather than covered>

## Concepts and their names across layers

## One concept, many names

## One name, many concepts

## Implicit concepts

## States and transitions

## Where business logic lives

## Unknowns
```

Name the commands you ran in one short list at the end.
