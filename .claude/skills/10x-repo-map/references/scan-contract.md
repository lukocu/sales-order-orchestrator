# Scan contract — shared ground truth for the sub-agents

Built by the main agent before dispatch and written to
`context/map/.work/scan-contract.md`. Four sub-agents run in parallel; they
must count the same commits, attribute files to the same capabilities and
ignore the same noise, or their results cannot be crossed in the report.

Keep it cheap: git, `git ls-files` and `rg` over names, no source reading.
Tracked files only; `-c core.quotepath=off` on every git command.

## Contents

```markdown
# Scan contract

- repo_root: <. or --root path>
- window: <since>..HEAD (effective: <first commit in window>..<HEAD date>)
- head: <short sha>
- trend_buckets: quarter | month | week
- commits_in_window: <n, merges excluded>
- commits_counted: <n after bot, agent and mass-commit rules>
- shallow_clone: <yes/no>
- forge_cli: <gh usable for owner/repo | not available>
- humans_in_window: <n distinct human authors>

## Module roots

<language>: <module roots> (also in .work/modules.txt)

## Noise filter

<pathspecs / regexes excluded from every count>

## Excluded and separated commits

bots: <n> — <rules that matched>
agent-authored: <n> — <identities> (counted as activity, never as people)
mass: <n> — <sha, files, reason> (full list in .work/excluded-commits.txt)

## Path history

<old path → current path for renamed or moved roots; deleted roots>

## Counting rules

<the rules below, restated with any repo-specific choices>

## Capabilities

<pointer to .work/capabilities.tsv and the inventory table — see capability-inventory.md>
```

## How to build it

**History once.** One `git -c core.quotepath=off log --since=<window>
--no-merges --name-status -M --format='@%H%x09%aN%x09%aE%x09%aI%x09%s%x09%(trailers:key=Co-authored-by,valueonly,separator=;)'`
pass into `.work/git-log.txt`. Every agent reuses it.

**Buckets.** Quarter when the effective window is 9 months or more, month
from 3 to 9 months, ISO week below 3 months.

**Module roots from manifests.** From `git ls-files`, every directory
holding a manifest is a module: `package.json`, `go.mod`, `Cargo.toml`,
`pyproject.toml`, `setup.py`, `Gemfile`, `composer.json`, `pom.xml`,
`build.gradle*`, `*.csproj`, `Package.swift`, `mix.exs` … The manifest type
gives the language. **A root manifest in a monorepo** owns only the files
outside every nested module; fold those by top-level directory (`.github/`,
`scripts/`, `docs/` …) and tag prose-only directories as `prose`. A repo with
a single root manifest gets its top-level source directories as modules.
Write the roots to `.work/modules.txt`.

**Noise by traits**, not by a hard-coded list, so it works in any stack:

- paths marked `linguist-generated` or `linguist-vendored` in
  `.gitattributes`, and committed build outputs (`dist/`, `build/`, `out/`,
  `target/`, `.next/`) when they appear in history;
- the lock or sum file next to each manifest;
- binary media and fonts (images, audio, video, `*.woff*`, `*.ttf`, PDFs):
  excluded from counts, their volume listed once per capability as context;
- snapshots (`__snapshots__`, `*.snap`) and recorded data fixtures (large
  JSON/YAML/CSV under `fixtures/`, `testdata/`). Hand-written test fakes and
  mocks are code — keep them;
- vendored dependency directories (`vendor/`, `third_party/` when vendored);
- generated code: files whose **first five lines** carry `Code generated`,
  `DO NOT EDIT`, `@generated` or `auto-generated`
  (`git grep -n -I -E '<markers>'`, keep matches with line number ≤ 5). A
  marker quoted further down a file is prose, not a generator.

Localisation catalogs (`i18n`, `locales`, `*.po`, `*.xliff`) are **kept and
listed**: they are often the repo-wide hub the history agent reports.

**Bots** are excluded from every count: author name ending in `[bot]` or
`-bot`, known automation identities (dependabot, renovate, github-actions,
release bots), and commits whose only change is a version bump of manifests
and changelogs. A `noreply` address alone is **not** a bot — forges use it for
humans and squash merges.

**AI agents as authors.** Commits whose _author_ is an AI coding agent
(Claude, Codex, Copilot, Cursor, Devin …) are **counted as activity** — the
code changed — but never as a person: they stay out of `humans_in_window`
and out of people evidence. Commits by a human author with an agent
`Co-authored-by` trailer are human commits. Record both counts.

**Mass commits — size plus a second trait.** Size alone cannot tell a
reformat from a big feature. A commit is mass when it is in the top ~1% by
files touched (and above 50 files) **and** either rename-dominated (most
entries `R` in `--name-status`) or its subject matches
`format|prettier|lint|rename|move|bump|license|reorg|migrate to|upgrade|import|sync|vendor|copy from|snapshot`.
List every exclusion with its reason; never exclude on size alone, and never
exclude a commit whose subject describes a feature.

**Path history.** For roots renamed or moved in the window (from the `R`
entries), record old → new so old paths fold into current modules and
capabilities. Roots that no longer exist at `HEAD` are listed as deleted and
reported, not silently dropped.

**Counting rules** — every agent uses exactly these:

- _Changes_ are counted per file: a commit touching files in three
  capabilities adds changes to each of the three.
- _Commits_ are counted once per capability they touch; a cross-cutting
  commit counts for every capability it touches. No "dominant capability"
  attribution.
- _Per-commit signals_ (fix share, reverts) count the commit for every
  capability it touches, and the evidence notes how many of them are
  cross-cutting (touching more than three capabilities).
- _Co-change_ uses the commits counted here and additionally drops commits
  touching more than half of all capabilities, reporting how many.

**Humans in window.** Count distinct human authors after the bot and agent
rules. With three or fewer, every concentration statistic is a baseline, not
a finding (see false-signals.md).
