# Research and planning task orchestration

Read before delegating or coordinating a multi-area investigation. The primary
skill owns its interview, output and persistence contracts. This procedure does
not require a separate skill, task API, model catalog or installed hooks.

## Choose the next operation

Keep a compact working list of unresolved questions: the decision each informs,
evidence already available, next lookup, owner and completion condition. Use the
host's task tracker when useful and available; otherwise use the conversation.
Do not create task files or bookkeeping calls for a single located lookup.

- **Located fact:** inspect the relevant source section locally. A delegate would
  add handoff and verification cost without removing independent work.
- **Independent evidence gap:** delegate when the parent can advance another
  unresolved question or an independent check adds material confidence.
- **Dependent gap:** finish its prerequisite first. Do not speculate in parallel
  about an interface or user decision that is still being settled.
- **User decision:** the parent asks using the primary skill's interaction rules;
  a child cannot infer consent or replace the user's product choice.

## Dispatch contract

In Claude Code, dispatch with the `Agent` tool (`Task` in older Claude Code
versions) — `subagent_type: "Explore"` for locating code, `"general-purpose"`
for analysis; in other hosts use the native equivalent.

Each child receives one bounded question, relevant paths and known findings,
current constraints/corrections, and an explicit completion condition. Specify
read-only work, no interviews, no lifecycle/artifact edits, and no further
delegation unless the parent deliberately assigns a further split. Require:

1. Answer and supporting file:line anchors or primary-source links.
2. What was actually inspected, including relevant source revision/changed files.
3. Uncertainty, contradictory evidence, and missing coverage.
4. A concise recommendation only if requested; no repeated repository overview.

Pass the necessary context, not the entire conversation or all skill templates.
Start with only the independent gaps that can be used now (usually one or two);
respect the host's concurrency limit. Avoid overlapping scans or having the parent
repeat a worker's search. Independent verification is a distinct task with a
reason, not an accidental duplicate.

## Capability and model choice

Use tools and selectors actually exposed by the host. Skill text does not enable
delegation or change the parent model. If selection is supported and permitted,
use a lighter available model for bounded discovery/extraction with checkable
anchors. Keep synthesis, conflicting evidence, architecture and security reasoning
with a sufficiently capable agent; a cheap profile is not a correctness argument.
Honor explicit user model choices. If no selector exists, use the available model
and report a material fallback; never claim routing occurred without native evidence.

On launch failure, inspect the concrete error. Retry only after a relevant input
or capability correction; do not repeatedly submit the same failed launch. If
delegation is optional, continue locally with the same scope and verification.
If explicitly required and unavailable, state the missing capability and stop the
dependent work. Report failed/cancelled workers as such, not completed research.

## Collect, verify and stop

Process returned findings as they arrive and continue work that does not depend
on outstanding results. Inspect decisive or conflicting source sections. Evidence
from a path locator is not proof of behavior; a summary is not a required full read.
Follow up with the existing worker for a specific remaining gap instead of opening
a fresh broad investigation.

When the user corrects scope or a factual assumption, invalidate only affected
findings. Update or cancel affected tasks; a late result based on superseded input
cannot restore the old decision. Keep unrelated verified evidence.

Finish discovery when the agreed questions have sufficient evidence for the next
decision and material contradictions are resolved. Close or cancel now-irrelevant
work; do not wait for optional exploration merely because it was started. An
unfinished required check remains an explicit gap, never a silent pass. Research
may report that limitation; a plan must resolve blocking decisions before approval
and finalization under its own contract.

After approval, investigate only a newly identified blocking gap; reuse the
approved findings for writing and save. When metrics exist, separate investigation,
interview, synthesis and persistence and include worker/retry overhead. Unknown
usage or cost remains unknown. Fewer workers or reads alone does not prove savings.
