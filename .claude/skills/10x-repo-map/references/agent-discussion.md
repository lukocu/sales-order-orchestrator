# Evidence brief: discussion

You are one of four sub-agents building a Project Map. Your source is
**what people say and argue about the code**: pull requests, reviews,
reverts, issues, planning artifacts and debt markers — the "buzz" around each
capability. Write `context/map/evidence/2-discussion.md` and return at most
15 lines.

Question: **where does the team spend its attention, friction and second
attempts?** A busy capability may be busy because it matters or because it
keeps breaking; discussion tells them apart.

Read first: the scan contract and `capabilities.tsv` in `context/map/.work/`,
and `<loaded-skill-dir>/references/false-signals.md`. Use the contract's
counting rules. Do not read source files.

## 1. Attribute PRs through git, not through the forge

PR numbers appear in squash and merge commit subjects (`(#123)`,
`Merge pull request #123`). Map each PR to the files of its commit in
`.work/git-log.txt` and so to capabilities. This works without the forge and
avoids heavy file listings over the API.

## 2. Forge signals — when the contract says `forge_cli` is usable

Use `gh` read-only, within the window, in small pages (`--limit 100`,
repeated with date ranges if needed). Never request per-PR file lists in bulk;
if a call times out, fall back to smaller pages or per-item `gh pr view`.

- `gh pr list --state all --search "created:>=<date>" --json
number,title,createdAt,mergedAt,closedAt,state,reviews,comments,additions,deletions`
  → per capability: PRs, PRs closed without merge, largest PRs, and **human**
  review activity. Comments and reviews posted by bots or automation accounts
  are not review (false-signal rule 7). If there is no human review at all,
  report that as a finding instead of medians.
- `gh issue list --state all --search "created:>=<date>" --json
number,title,labels,createdAt,closedAt,state` → per capability (labels,
  title vocabulary): opened, still open, bug-labelled, age of open bugs.
- Never post, comment, label or change anything on the forge.

## 3. Git-only signals — always

- Reverts (`Revert "…"`, `revert:`) and hotfix subjects, traced to the
  capability they were about (false-signal rule 12).
- Second attempts: the same scope fixed several times within days, or
  revert → re-land pairs.

## 4. Planning and debt markers

- Planning artifacts wherever the repo keeps them (`context/changes/`,
  `context/archive/`, ADRs, RFCs, `docs/decisions/`) — attribute each to a
  capability by name, skipping archived analyses such as
  `context/archive/*-repo-map/` and `*-domain-distillation/`; count per capability and note which are recent.
- Debt markers at `HEAD`: `rg -c 'TODO|FIXME|HACK|XXX'` over each
  capability's tracked files (counts only, no reading), normalised per 1000
  lines.
- Prose churn in docs and plans counts here as discussion about the
  capability it names (false-signal rule 8).

## Evidence file

```markdown
# Evidence: discussion

<sources available: gh (owner/repo) or git-only; window; limits hit>

## Buzz per capability <!-- one table: PRs, closed-unmerged, human review, reverts, open bugs, plans, markers -->

## Friction <!-- reverts, second attempts, long-open bugs, closed-unmerged PRs, with numbers -->

## Planning attention <!-- which capabilities attract plans and research -->

## Debt markers

## Mechanical signals <!-- demoted by false-signals.md, and why -->

## Unknowns <!-- e.g. no forge access, issue tracker elsewhere, production errors not visible -->
```

Production error trackers are out of scope for this run; list them under
Unknowns when the repo shows one is used. Name the commands you ran in one
short list at the end.
