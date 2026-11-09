# Source inventory — shared ground truth for the sub-agents

Built by the main agent before dispatch, as two files:

- `context/domain/evidence/0-sources.md` — what the code is and where it
  lives. Read by every sub-agent.
- `context/domain/evidence/0-documents.md` — the domain documents and the
  product goals. Read by the docs agent and the synthesis only.

The split protects independence. The code agents must not learn the
documents' vocabulary first, or "the code uses the same word" stops meaning
anything. Write `0-sources.md` with **no domain vocabulary**: no entity
names, no term lists, no document summaries — paths, layers, stacks and
reasons only.

Keep both cheap: file listings, headings, short passages. Full reading is the
sub-agents' job.

## `0-sources.md` — code scope, stack and layers

```markdown
# Sources: code

- repo_root: <absolute path>
- code_scope: <. or --root path, or the application chosen in preflight>
- head: <short sha> (dirty: <paths> | clean | not a git repository)
- path_alias: <optional, e.g. app/ = apps/shop/src/>

## Stack

<language and framework, one line each>

## Layers

| layer | path patterns | notes |

## Excluded

| path | reason |
```

**Layers**, as path patterns inside the code scope:

- **entry points** — routes, controllers, handlers, CLI commands, jobs and
  their schedule configuration, queue consumers, webhooks;
- **application logic** — services, use cases, commands, workflows;
- **domain types** — models, entities, records, structs, value types;
- **persistence** — schema files, migrations, ORM models, queries, database
  functions and policies;
- **UI** — pages, screens, components, client state, translation and copy
  files;
- **tests** — where they live and how they are named.

A layer that does not exist in this codebase is written as such; a codebase
without a separate domain layer is a finding, not a gap.

**Excluded**, each with a reason:

- `context/domain/` itself and archived distillations
  (`context/archive/*-domain-distillation/`) — earlier distillations and
  other domain analyses would feed a previous run's conclusions back in as
  evidence;
- packages and apps outside the code scope;
- developer tooling that is not the product: build and release scripts,
  internal code-review or lint tools, CI helpers, agent configuration —
  except agent instruction files that describe the product (`CLAUDE.md`,
  `AGENTS.md` explaining business flows): list those as _reference_
  documents, read by the docs agent only;
- generated code and vendored dependencies.

## `0-documents.md` — domain documents and goals

Use `--docs` when given. Otherwise discover from the repository root, in this
order, and stop listing a family once it is clearly covered:

1. **Requirements and vision** — product requirements, PRD, specification,
   vision, goals, user stories, use cases, acceptance criteria; a `docs/`,
   `spec/`, `requirements/` or project-context directory (in this toolkit's
   convention, `context/foundation/`).
2. **Narrative and history** — change folders, roadmaps, ADRs and RFCs,
   changelogs written for people, archived plans (`context/changes/`,
   `context/archive/`, `docs/adr/`). They carry the vocabulary the team used
   over time. Record how many there are.
3. **Reference** — README, glossaries, user-facing help or FAQ content,
   standalone API specifications (OpenAPI or GraphQL files), seed and example
   data that use business words. An API description embedded in source code
   is code, not a document.
4. **Engineering** — test plans, stack decisions, team lessons, runbooks.
   Read for rules only.

Classify each document by kind with its path and a short description of what
it is about — in neutral words, without copying its terms into `0-sources.md`.

When only a README (or nothing) exists, say so at the top: the code carries
the language, and every invariant will rest on code and naming alone. That is
a limitation, not a failure.

**Product goals.** Quote, with `path:line`, what the product is for: goals,
success criteria, value proposition, target users, non-goals. Keep **product
goals** apart from **change goals** — a requirements document written for
one change states that change's goals, not the product's. When only change
goals exist, write so: the synthesis then judges the Core from the product
description and usage. Without any goals, write "no stated goals".

```markdown
# Sources: documents

- documents: <n requirements, n narrative, n reference, n engineering>

## Domain documents

| path | kind | what it is about |

## Product goals

<quotes with path:line, or "no stated goals">

## Change goals

<goals of single changes, quotes with path:line — not used to judge the Core>

## Limitations
```
