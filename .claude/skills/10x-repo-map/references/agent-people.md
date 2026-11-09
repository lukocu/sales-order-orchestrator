# Evidence brief: people

You are one of four sub-agents building a Project Map. Your source is
**authorship in git history**, per business capability. Write
`context/map/evidence/4-people.md` and return at most 15 lines.

Question: **whom to ask about each capability before a change somebody may
already have tried?** Not `git blame` ("who changed this line") — people
grouped by the kinds of problems they worked on.

Read first: the scan contract and `capabilities.tsv` in `context/map/.work/`,
and `<loaded-skill-dir>/references/false-signals.md`. Use the contract's
excluded commits and agent rule (bots are out; agent-authored commits are
activity, not people). Reuse `.work/git-log.txt`. Do not read source files.

## 1. Areas

All capabilities rated high or medium criticality in the inventory, plus any
other capability in the top 5 by counted changes. One line each on why.

## 2. People per capability

- Human authors of the last window per capability. `%aN` applies `.mailmap`;
  when identities clearly duplicate (same name, different e-mails), merge
  them using e-mails privately — never write an e-mail into the evidence
  file.
- A human author with an agent `Co-authored-by` trailer stays — the human
  steered the change. Report the share of agent-co-authored commits per
  capability as context, not as a filter.
- Per capability: 1–4 people, each with topic groups from commit subjects and
  touched paths ("schema migrations", "permission edge cases", "render
  performance") and their active period.

## 3. Concentration — against the baseline

Use `humans_in_window` from the contract (false-signal rule 6). With three or
fewer humans, report "small team — concentration is the baseline" and skip
bus-factor language; list instead which capabilities only one person has
ever touched. With a larger team, mark a capability concentrated when one
person carries most of its commits **and** that is well above the team-wide
share.

## Privacy

Display names only, never e-mail addresses. Describe work, not people.

## Evidence file

```markdown
# Evidence: people

<humans in window, baseline, filter notes>

## People per capability <!-- names, topic groups, period -->

## Concentration <!-- relative to the baseline -->

## Agent co-authorship <!-- share per capability, as context -->

## Implications <!-- whom to ask before what kind of change, which PRs to read -->

## Unknowns <!-- who is still on the team, formal ownership -->
```

Name the commands you ran in one short list at the end.
