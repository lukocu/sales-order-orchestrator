# Capability inventory — what the product does

The backbone of the report. Built by the main agent as part of the scan
contract, before dispatch. Every sub-agent attributes its evidence to these
capabilities, so a wrong cut here distorts everything downstream: give each
capability its evidence and keep unassigned code visible.

A **capability** is something the product does for a user, an operator or an
integration — "checkout", "order fulfilment", "billing & invoices",
"sign-in", "workspace management", "search", "notifications", "reporting",
"public API & webhooks" — not a layer or a folder. It usually spans route +
service + data + UI + tests across several directories.

## Signals — all cheap, all stack-agnostic

Collect each into `.work/` and condense; do not read source files.

1. **Commit vocabulary.** Count scopes and leading nouns in commit subjects
   (`feat(billing):`, `fix(auth):`, `search:`, `[orders]`). Where the team
   labels its own work, this is the strongest naming signal.
2. **Entry points.** List, by convention for the stacks in the scan contract:
   page and route directories (`pages/`, `app/`, `routes/`, `views/`),
   API endpoints and controllers, CLI commands (`cmd/`, `bin/`, command
   registries), scheduled jobs, queue consumers and webhooks, worker
   entrypoints. Names of routes and commands are names of capabilities.
3. **Data model.** Table and collection names from migrations and schema
   files (`rg -o` over `create table`, model declarations). Tables cluster
   into capabilities (`orders`, `order_items`, `shipments` → order
   fulfilment).
4. **The project's own words.** Headings of README, agent instruction files,
   `docs/`, product docs, and names of planning folders (`context/changes/*`,
   ADRs, RFCs). Read headings and file names, not prose.

## Building the inventory

- Name **8–15 capabilities** in user-facing language. Merge synonyms across
  signals (a commit scope `billing`, a route `/billing/*` and tables
  `invoice*` are one capability).
- Add three non-business buckets so nothing hides: **platform &
  infrastructure** (CI, deploy, release tooling, shared config), **shared
  foundations** (design system, shared libs, types used everywhere) and
  **docs & planning** (prose only).
- Write each capability's **footprint** to `.work/capabilities.tsv`, one
  pattern per line: `<pattern><TAB><capability id>`. A pattern is either a
  **path prefix matched on whole path segments** (`src/billing` matches
  `src/billing/x.ts`, not `src/billing-legacy/`) or a **glob** containing
  `*` (`db/migrations/*invoice*`). Globs win over prefixes; among prefixes the
  longest wins. Use globs for shared directories that hold every capability's
  files by name — migrations, routes tables, locale files, test suites.
  Files matching nothing are `unmapped`.
- Check coverage on business capabilities, not on the catch-all buckets:
  report the share of counted changes in `unmapped` **and** in each
  non-business bucket. If unmapped exceeds ~10% or the catch-alls together
  exceed ~40% of code changes, refine the footprints once; report what
  remains.

## Criticality

Rate each capability **high / medium / low** from fixed criteria, and name
the criteria that apply — never from intuition:

- money moves through it (payments, billing, entitlements);
- identity or access (sign-in, sessions, permissions, gating);
- user data is created, changed or deleted;
- it delivers the product's core value (the reason users come: for a shop,
  catalog and checkout; for a collaboration tool, the shared workspace; for a
  data product, ingestion and reports);
- exposure: public or unauthenticated entry points, external integrations,
  webhooks;
- other capabilities depend on it at runtime.

Infrastructure is rated by what it can break (a deploy pipeline that can take
production down is high), not by how often it changes.

## In the scan contract

```markdown
| id | Capability | What it does (one line) | Criticality (criteria) | Footprint (main patterns) | Evidence |
```

The table and the TSV are an `inference` built from signals; say which
signals named each capability. List the coverage figures under the table.
