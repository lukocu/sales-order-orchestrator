# False signals — check before calling anything a risk

Every rule here describes a way real maps ranked noise as risk. Sub-agents
apply them to their own evidence; the report applies them again when it
crosses sources. A false signal is not deleted — it is reported as
**mechanical**, with the reason, and kept out of risk ranking.

1. **Build outputs and tooling edges.** An import of `dist/`, `build/` or a
   package's compiled entry from a script, or a cycle formed only through
   build or release tooling, is build order, not architecture. Plain scripts
   often must import built output to consume a workspace package. Nobody
   reads `dist/`.
2. **Config written as code.** Dozens of files importing one `define*`
   helper, registry or schema (route tables, plugin manifests, feature-flag
   lists, form definitions) is fan-in by design. If a validator or a strict
   build catches a breaking change, it is cheap coupling — note it, do not
   rank it.
3. **Workflow lockstep guarded by the build.** Two areas that always change
   together because the workflow says so (a new endpoint plus its generated
   client, a migration plus its schema snapshot, a translation key plus its
   catalog entry) are a corridor, not a hidden contract — if the build or a
   check fails loudly when they drift. Check for that guard before calling it
   fragile.
4. **Shared cause counted twice.** "All sources agree" only counts when the
   sources are independent. A CI file is a co-change hub _because_ every new
   check touches it; its owner carries it _because_ one person does infra; a
   new subsystem is both busy and heavily planned _because_ it is being
   built. Name the common cause and count it once.
5. **Trial-and-error fix ratio.** CI, deploy, infrastructure config and UI
   polish get fixed by iteration (`fix(ci): make the pipeline green`,
   `fix: spacing`). A high fix ratio there is how that work is done, not
   evidence of a broken capability. Read the subjects before ranking.
6. **Team-size baseline.** With three or fewer humans in the window, "one
   person carries 80%" is normal. Report concentration only relative to the
   team, and say the baseline.
7. **Bots, agents and regeneration.** Version bumps, generated clients and
   regenerated lockstep files are churn without decisions. Bot commits are
   excluded in the scan contract; agent-authored commits are activity, not
   people. Status comments posted by automation on PRs are not review.
8. **Prose and planning churn.** Changes in docs, plans, ADRs and agent
   notes are discussion about capabilities, not code activity. Attribute them
   to the capability they discuss (discussion evidence), never rank a docs
   folder as a hot area.
9. **Type-only edges.** `import type` and equivalent compile-time-only edges
   inflate cycles and fan-in. Keep them separate from runtime edges when the
   graph source can tell.
10. **External consumers.** If the repo exposes an API, published package or
    contract, its consumers may live in other repositories. A missing
    consumer inside the repo is `unknown (external)` — never pair the
    contract with an in-repo module just because one exists.
11. **History that no longer exists.** Hot files that were deleted or moved
    describe the past. Report them as such; fold renamed paths into their
    current capability.
12. **Spillover from one big commit.** A single large revert or migration
    touching many capabilities inflates fix and revert counts of every small
    capability it brushed. Attribute it to the capability it was about and
    note the spillover elsewhere.
