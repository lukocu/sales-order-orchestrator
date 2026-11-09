# The report — `context/map/repo-map.md`

Written by the main agent from the four evidence files and the capability
inventory. The evidence holds many signals but is not yet a map. The map is a
**synthesis of evidence about the business**: which capabilities exist,
which matter, which are under pressure, and why. Keep the seven sections
below stable — later work reads **Risk zones**, **First day** and
**Limitations** by name.

## Role and inputs

Act as an engineer helping someone get up to speed in a large legacy repo as
fast as possible — a new team member, someone returning to a module after a
long break, or a team inheriting a repo. Build the report only from the
scan contract (with its capability inventory) and:

- `context/map/evidence/1-history.md`
- `context/map/evidence/2-discussion.md`
- `context/map/evidence/3-structure.md`
- `context/map/evidence/4-people.md`

Do not generate new data and do not repeat their tables in full. A missing or
partial evidence file is a gap to state in Limitations.

## Ranking: criticality × buzz

For each capability:

- **Criticality** — from the inventory (high / medium / low, with criteria).
- **Buzz** — from independent signal families, each high / medium / low
  relative to the other capabilities:
  - _change_: activity and a rising trend (history);
  - _fix pressure_: fix share and reverts (history);
  - _friction_: human review rounds, reverts, second attempts, open bugs,
    closed-unmerged PRs (discussion);
  - _attention_: planning artifacts and prose about it (discussion);
  - _reach_: runtime blast radius and real cycles (structure).
- **Independence check** — before counting two families as agreement, ask
  whether one cause explains both (false-signal rule 4). Count a shared cause
  once and say so.

A capability is a risk zone when criticality is high and buzz is high in at
least two independent families, or criticality is medium and buzz is high in
three. Report **as many risk zones as qualify, at most six** — never fill a
quota. A capability that misses the bar narrowly may be listed once as
_watch_, clearly separated. Apply [false-signals.md](false-signals.md) once
more: mechanical signals never put a capability in a risk zone; they go to
"Looks hot, is not".

## Rules

1. Join the perspectives into one picture per capability: what it does →
   how much buzz → how far a change reaches → whom to ask.
2. Show where the folder structure does not match the capabilities (one
   capability across many folders, one folder serving several capabilities).
3. Lead from the capability table to 5–8 "first files to read".
4. State the limits plainly: the window, git-only vs forge, graph coverage,
   capability coverage (unmapped and catch-all shares).
5. For every coupling, say how you know it: runtime graph, co-change, or an
   area no tool covered. A layer without a graph is `unknown`, not "no
   connections"; an absent in-repo consumer of a public contract is
   `unknown (external)`.
6. Mark couplings that exist through regeneration, workflow lockstep or
   tooling as mechanical — cheaper than hand-kept contracts.
7. Name contradictions as questions: a capability with high buzz but low
   reach, a hand-kept pair with no co-change, a critical capability nobody
   discusses.

## Structure

```markdown
---
artifact: repo-map
generated: <YYYY-MM-DD>
repo_root: <from the scan contract>
history_window: <since..HEAD @ sha, effective range>
evidence_sources: <git | git + gh (owner/repo)>
graph_coverage: <language: source, confidence — per language>
evidence: context/map/evidence/
---
```

1. **TL;DR** (5–7 sentences) — what the product does, its main capabilities
   (Mermaid from the structure agent's capability graph — not drawn by hand;
   if none exists, list them instead), where the buzz is, where it hurts.
2. **Terrain** — the capability table: capability · what it does ·
   criticality · buzz per family · trend · where it lives. Then
   infrastructure, shared foundations and docs as short lines, and the
   coverage figures.
3. **Real couplings** — between capabilities: runtime edges, co-change
   pairs, contracts; each with its source and whether it is mechanical.
4. **Risk zones** — the qualifying capabilities (or a capability's
   sub-area), each: one line of why, the independent signals behind it, the
   files where it lives. Then _watch_ items if any, and a short **Looks hot,
   is not** list for demoted signals.
5. **Whom to ask** — per zone: 1–2 people with topic match, against the
   team-size baseline.
6. **First day** — an ordered list of 5–8 entry files or modules: per top
   capability, its entry point and where the logic actually lives.
7. **Limitations** — window, sources available, graph coverage, capability
   coverage, failed or partial agents, what the map does NOT say, and the
   unknowns worth a focused investigation.

Format: Markdown with Mermaid, concise, tables only where they help. Goal:
after 15 minutes of reading, the reader knows what the product does, where
it is under pressure, what is dangerous and where to start. Write in the
report language chosen in preflight.

Section headings are fixed per language, because later work finds sections
by these exact names. English: TL;DR, Terrain, Real couplings, Risk zones,
Whom to ask, First day, Limitations. Polish: TL;DR, Teren, Realne
powiązania, Strefy ryzyka, Kogo zapytać, Pierwszy dzień, Ograniczenia. In any
other language, keep the English headings.

Optional appendix, **only if the user asks** — a module legend for the files
in Risk zones and First day: role (core / supporting / peripheral), depth
(deep / shallow), change profile (stable / volatile / seasonal), blast radius
(load-bearing / contained), sensitivity (high / medium / low), each with
evidence, hypotheses marked `needs verification`.

## Verification

One pass over the written report before presenting it:

- every capability in Risk zones has criticality evidence and at least two
  independent buzz signals pointing to evidence-file lines;
- no risk zone rests on a signal listed as mechanical in any evidence file;
- every path in First day and Risk zones exists at `HEAD`
  (`git cat-file -e HEAD:<path>`);
- every Mermaid diagram comes from evidence (the capability graph) and is
  syntactically plausible;
- every `unknown` in the evidence files is carried into Limitations or
  dropped with a reason.

Fix what fails; do not re-run the sub-agents for a wording problem.
