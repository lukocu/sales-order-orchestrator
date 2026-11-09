# Evidence brief: history

You are one of four sub-agents building a Project Map. Your source is **git
history**, attributed to business capabilities. Write
`context/map/evidence/1-history.md` and return at most 15 lines.

Question: **which capabilities are changing most, which are getting fixed
most, and which change together?**

Read first: the scan contract and `capabilities.tsv` in `context/map/.work/`,
and `<loaded-skill-dir>/references/false-signals.md`. Use the contract's
window, buckets, excluded commits, path history and **counting rules** for
every number; reuse `.work/git-log.txt`. Do not read source files. Use
`-c core.quotepath=off` on git commands.

## 1. Activity per capability

- Changes and commits per capability (patterns from `capabilities.tsv`:
  globs first, then the longest whole-segment prefix; renamed paths folded via
  the path history). Show the unmapped share and agent-authored share.
- Inside the top capabilities, the TOP files — so a capability is not a black
  box.

## 2. Trend

- Per capability, in the contract's buckets. Label each **constant**,
  **rising**, **fading** or **seasonal**, and name the campaign behind a spike
  when commit subjects make it obvious.

## 3. Fix pressure

- Per capability: the share of commits whose subject matches
  `fix|bug|hotfix|revert|regression|broken|incident` (or a bug-labelled issue
  reference), and reverts as their own count, with the number of
  cross-cutting commits among them. State the heuristic.
- Before ranking, apply false-signal rules 5 and 12: read the fix subjects of
  infrastructure and UI-heavy capabilities, and trace big reverts to the
  capability they were about.

## 4. Co-change between capabilities

- Per commit, the set of capabilities touched (co-change rule from the
  contract); count pairs. Report **support** and **confidence** (shared ÷
  commits of the less active side).
- **Hub files**: files co-changing with the most distinct capabilities
  (count only partners seen in at least two commits). Say what each is
  (translations, shared config, schema, generated client) and apply rules 3,
  4 and 7.
- **Freshness**: `git cat-file -e HEAD:<path>` for every file you name;
  report deleted or moved ones (rule 11).
- What co-change cannot show: capability pairs that should change together
  but do not (a backend model and a hand-kept frontend twin) — list them as
  unknowns.

## Evidence file

```markdown
# Evidence: history

<window, buckets, commits counted, excluded — from the contract>

## Activity per capability <!-- changes, commits, share; unmapped and agent-authored shares -->

## Top files in top capabilities

## Trend <!-- table + labels + campaigns -->

## Fix pressure <!-- fix share, reverts, cross-cutting, heuristic -->

## Co-change between capabilities <!-- support, confidence -->

## Hub files and freshness

## Mechanical signals <!-- what false-signals.md demoted, and why -->

## Unknowns
```

Name the commands you ran in one short list at the end.
