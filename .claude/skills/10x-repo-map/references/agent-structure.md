# Evidence brief: structure

You are one of four sub-agents building a Project Map. Your source is the
**static dependency graph**, read per business capability. Write
`context/map/evidence/3-structure.md` and return at most 15 lines.

Question: **how far does a change in each capability reach, and where are
its boundaries broken?** The graph explains capabilities; it does not rank
them.

Read first: the scan contract and `capabilities.tsv` in `context/map/.work/`,
and `<loaded-skill-dir>/references/false-signals.md`. Tracked files only.
**Install nothing.**

## 1. Graph source per language — fallback chain

For each language in the scan contract, take the first source that works and
record the level:

1. **Already in the repo** — the project's own graph tooling (dependency
   rules in config, module boundaries enforced by the build, graph scripts in
   manifests or CI).
2. **The project's toolchain** — compilers and package tools already
   installed, globally or in the project's own dependencies (a compiler API
   inside installed project dependencies counts): `go list -deps -json ./...`,
   `cargo metadata`, `jdeps`, `mvn dependency:tree`, `dotnet list reference`,
   the TypeScript compiler API …
3. **A dedicated tool already on this machine** — see
   [graph-tools.md](graph-tools.md). Run it if present, never install it.
4. **Universal fallback** — import statements via `ast-grep` (or `rg`) with
   relative imports resolved to files. `confidence: low`; list what it cannot
   resolve (aliases, re-exports, dynamic imports).

One graph per language; never let one stack stand in for the repo. Name a
level-3 tool worth installing under Unknowns.

## 2. Normalize, then fold to capabilities

Write file-level edges to `context/map/.work/edges-<lang>.csv` with columns
`from,to,kind`:

```csv
from,to,kind
src/orders/service.ts,src/payments/client.ts,runtime
src/orders/types.ts,src/shared/money.ts,type
scripts/release.mjs,packages/core/dist/index.mjs,build
```

Repo-relative paths, external packages removed, tests and generated code
excluded unless a question is about them. `kind` is `type` for
compile-time-only edges (false-signal rule 9), `build` for edges into
`dist/`/`build/` outputs or from build and release tooling (rule 1),
`runtime` otherwise.

Compute signals with the bundled script:

```sh
S=<loaded-skill-dir>/scripts/graph-metrics.mjs
node $S --help
node $S context/map/.work/edges-<lang>.csv --modules context/map/.work/capabilities.tsv --kind runtime
node $S context/map/.work/edges-<lang>.csv --modules context/map/.work/capabilities.tsv --kind runtime --unmapped group --emit mermaid
node $S context/map/.work/edges-<lang>.csv --kind runtime --focus <file-or-prefix> --direction both --depth 1 --emit mermaid
```

`--modules` reads `capabilities.tsv` with the same semantics the inventory
defines (globs first, then the longest whole-segment prefix) and reports how
many files stayed unmapped. The output gives **Ca** (how many depend on it),
**Ce** (how many it depends on), **instability = Ce / (Ca + Ce)**, cycles,
entry candidates and leaves.

## 3. Answer per capability

Markdown tables, no Graphviz/DOT.

1. **Capability graph** — runtime edges between capabilities with Ca, Ce and
   instability. Emit it as Mermaid (≤ 20 nodes): this is the grounded diagram
   the report uses.
2. **Blast radius** — for each high-criticality capability: who depends on
   it at runtime (incoming), what it depends on (outgoing), which contracts
   other capabilities import from it.
3. **Cycles** — runtime cycles inside and between capabilities, smallest
   real loop named explicitly (a 2-file cycle inflated to 10 nodes by
   type-only edges is a 2-file cycle). Type-only and build cycles go to
   Mechanical signals.
4. **Broken boundaries** — infer the intended layering per capability
   (foundation types → data access → features → entry points) as
   `inference`, list runtime edges against it.
5. **Test risks** — where a capability will be hard to test in isolation
   (pulls a data/API client, global state, many shared utils): heavy mocking
   vs integration vs e2e.
6. **Centres and thin entry points** — high Ca with low instability suggests a
   load-bearing contract; an entry candidate that only delegates is a thin
   entry point, not the core. Apply false-signal rule 2 to fan-in from
   config-as-code.

## Evidence file

```markdown
# Evidence: structure

## Graph sources <!-- per language: source, level, confidence, blind spots -->

## Capability graph <!-- table + Mermaid -->

## Blast radius per capability

## Cycles <!-- runtime only; smallest real loop -->

## Broken boundaries

## Test risks

## Centres and thin entry points

## Mechanical signals <!-- build, type-only, config-as-code edges, with counts -->

## Unknowns <!-- runtime coupling (DI, reflection, dynamic imports, flags, codegen, queues,

                             webhooks), external consumers, languages without a graph, tools worth installing -->
```

Name the commands you ran in one short list at the end.
