# Subagent briefs

Fill the `{{…}}` slots and launch all auditors in one message so they run in
parallel. Subagents start with no context: the capture model and known
issues are what keep them from re-deriving the basics and from
re-reporting what is already tracked.

## Area auditor (one per flow, read-only)

```
You are auditing the **{{AREA_NAME}}** flow of {{PROJECT_ONE_LINER}}
(repo: {{REPO_PATH}}) for code logic that makes production errors hard to
monitor and diagnose. READ-ONLY: do not edit files, do not commit.

## Capture model (already established — do not re-derive; verify only if you doubt it)
{{CAPTURE_MODEL}}

## Known issues (don't re-report; say if your finding explains one)
{{KNOWN_ISSUES_OR_NONE}}

## Symptom reported by the user
{{SYMPTOM_OR_NONE}}

## Your scope
{{AREA_DESCRIPTION}} — full stack: UI/client code, API/handlers, services,
data access, external calls, background work triggered by this flow.
Entry points to start from: {{ENTRY_POINTS}}. Find the rest by searching and
following calls.

## What to hunt for
Use these categories: coverage-gap, swallowed, logged-not-captured,
flattened-response, missing-throw, identity-lost, missing-context, config,
noise. {{TAXONOMY_SUMMARY}}

Pay special attention to failures that don't look like failures:
redirects, 2xx with an error flag, errors inside streams, fallbacks/empty
states, "not found"/"no access" that could really be an outage.

## Rules
- Audit application code. Assume logs and the error tracker are collected
  in production. Don't report missing platform/dashboard settings (logging
  not enabled in deploy config, no log forwarding, no alert rules). They can
  live outside the repo. At most mention one in a closing "assumptions"
  line.
- Verify every claim by reading the code; cite file:line.
- Skip cases a comment clearly justifies, but note if the justification
  still leaves a monitoring gap.
- Signal over volume: ~10–25 findings, sorted by severity
  (critical = a real production failure in this flow would be invisible or
  undiagnosable).

## Output
For each finding: location, category, severity, what happens in production
(user-visible and responder-visible), one-line fix direction. End with 3–5
bullets on the systemic patterns in this flow.
```

## Plumbing auditor (one per run, read-only)

```
You are auditing the **cross-cutting observability code** of
{{PROJECT_ONE_LINER}} (repo: {{REPO_PATH}}). READ-ONLY. Other agents cover
the feature flows ({{AREAS}}); you cover the shared code they all run
through: tracker init, boundaries, middleware, logger, error helpers.

Assume logs and the error tracker are collected in production. Platform or
dashboard settings (log collection, log forwarding, alert rules) are often
configured outside the repo, so their absence in config files is
**unknown, not missing**. List those under "assumptions" and never as
findings or root causes. Your job is what the code does to errors before
they reach that pipeline.

## Capture model so far
{{CAPTURE_MODEL}}

## Symptom reported by the user
{{SYMPTOM_OR_NONE}}

## Answer with evidence (file:line, and dependency source when behaviour depends on a library version)
1. Uncaught exceptions in request handlers/pages: do they reach the
   tracker as exceptions with stacks, or does the framework convert them
   into error responses first? Also streamed/SSR bodies.
2. Code before the tracker boundary (middleware order, filters, app
   bootstrap): captured anywhere?
3. Handlers outside the boundary: what happens when they throw, and when
   they return a 5xx without throwing?
4. Status-based fallbacks (e.g. "report every 5xx"): grouping, cardinality
   of route tags, double reporting.
5. Scrubbing/privacy hooks: do they strip or rewrite things needed for
   diagnosis (stack frames, file names, breadcrumbs, release, causes, error
   codes)? How does the logger serialize error objects?
6. Release/version and environment: does the init *code* set them where
   the SDK needs them from code? Are preview/staging events separable?
   (Build/upload steps you can't see may happen in CI or the dashboard;
   treat that as an assumption.)
7. Client side: global handlers, error boundaries, framework hydration
   or chunk-load handling, is the tracker loaded on every page/layout?
8. Background work: jobs, queues, cron, post-response tasks, separate
   workers — tracker init and failure reporting.
9. Repo-wide sweep (exclude tests): counts of empty catches, catch-without-
   binding, promise catch-to-default, raw console/print error logging,
   error-level log calls, and errors thrown without cause. List the ~10
   most consequential examples *outside* {{AREAS}}.
10. Given that the platform collects logs and invocation outcomes: which
    code-level failures still leave nothing useful in them? Look for a
    request that ends 200/3xx, a log line without the error object, or an
    exception caught before the runtime could record it.

## Output
Answers 1–10 with evidence and a verdict each; then findings
(location, category, severity, production impact, fix direction); then
3–5 systemic root causes, each a code mechanism with file:line; then a
short "assumptions" list of outside-repo settings you could not confirm.
```

## Runtime prober (optional, isolated)

Launch with `isolation: "worktree"` (or instruct it to create a temp
clone). Give it `references/runtime-probes.md` content and the path to
`scripts/fake-ingest.mjs`.

```
You are running **runtime experiments** to see which production failures are
captured vs missed. Repo: your isolated copy of {{REPO_PATH}}. You MAY edit
files in this isolated copy to inject failures. Never touch the original
working tree, never commit, push or deploy, never send events to a real
error tracker, never use production databases or third-party accounts.

## Capture model
{{CAPTURE_MODEL}}

## Procedure
{{RUNTIME_PROBES_REFERENCE}}

## Probe catalog (at minimum; skip shapes that don't exist in this stack)
{{PROBE_CATALOG}}

## Output
Table: probe id | failure shape | response | platform console | tracker
(sent? exception vs message? stack? tags?) | verdict (good / poor /
missed). Mark each row observed vs inferred. List exact blockers for
anything not tested, every file changed, and the command that reruns the
suite.
```
