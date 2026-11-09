# SHA diagnosis and repointing before archive

Run this read-only procedure before the archive confirmation. Missing evidence is a warning, not proof of a squash. Never use the current branch or `HEAD` as the integration target merely because the archive runs there.

## Resolve and refresh the integration target

1. Find the implementation PR associated with the change, using recorded PR links or commit associations. Inspect its base repository and base branch, state, merge commit, commit list, and diff (for GitHub, `gh pr view <number> --json url,state,baseRefName,mergeCommit,commits,files` and `gh pr diff <number>` in the PR repository, identified by its URL). Discover associations from the change and its SHAs, not only the currently checked-out branch, so running on main and on an old feature branch produces the same target. A plan-only PR is not an implementation PR. Ambiguous associations require clarification.
2. Use that PR's base branch in its base repository when available. Otherwise resolve the relevant remote's default branch with `git ls-remote --symref <remote> HEAD`. A cached `refs/remotes/<remote>/HEAD` is only a hint, not a fresh result. If the remote or branch cannot be established, ask the user to identify it or continue archiving with a warning and no repointing. Never guess `main` or `master`.
3. Refresh only the target ref with `git fetch --no-tags <remote> +refs/heads/<base>:refs/remotes/<remote>/<base>`, without checking out any branch. Resolve its commit OID and record it as the target snapshot. If fetch fails, warn that history is unavailable; do not diagnose against a stale ref or recommend repointing. Quote resolved arguments when executing commands.

## Classify existing SHAs

Within `## Progress` only, collect completed `- [x]` rows ending in ` — <sha>` (7+ hexadecimal characters). Keep each row ID and original suffix; deduplicate SHAs for checks, not rows for approval. Leave pending and SHA-less rows out of this procedure.

- Resolve each suffix to a unique commit with `git rev-parse --verify '<sha>^{commit}'`. Distinguish a missing object from an ambiguous abbreviation, non-commit object, or command/repository error; inspect the diagnostic rather than treating every nonzero result as missing. Report these separately.
- For a resolved commit, run `git merge-base --is-ancestor <resolved-sha> <target-oid>` and inspect the exit code: **0** = present in target history, **1** = not in target history, **anything else** = check failed. Retain SHAs already in history, including ordinary merges.
- In a shallow or incomplete repository, a negative ancestry result is inconclusive until relevant history is fetched/deepened successfully. If it cannot be completed, report incomplete history instead of “not integrated”. Missing objects likewise do not prove a squash. Show affected row IDs and the actual failure reason; with incomplete data, warn without recommending replacement.

Every SHA diagnostic names the commit: short SHA plus subject from `git log -1 --format='%h %s' <sha>` (for a missing object, the suffix as written and `object missing`), the affected row IDs, and the target ref with its snapshot OID — for example `Row 1.1: 40b1647 "feat(x): add Y (p1)" is not in origin/master @ 137fc16`.

## Establish the integration commit

For resolved SHAs conclusively outside the complete target history, inspect the associated **merged implementation PR**. Its merge commit is a candidate only when the PR commit list links the old SHAs to it and the PR diff plus the candidate's diff demonstrate that it integrates the implementation covered by those rows. Inspect the actual code changes, not only filenames. Several unrelated PRs or changes cannot be mapped wholesale to one commit.

`git log -- <change-folder>` may locate candidates, but a commit that only added or moved the plan is not proof of implementation integration. A plan merged before the code must not be mistaken for the implementation squash.

If the association is not unambiguous, show candidate SHA, title, changed-file summary and relevant diff scope, then ask the user to identify or confirm the integrating commit and which rows it covers. No candidate → ask for a commit or allow archive without repointing. User confirmation supplies the association, not missing history: resolve that commit and verify ancestry against the refreshed target snapshot (exit 0 required). If any required check fails or data remains incomplete, keep the affected rows unchanged and report why; do not recommend repointing them.

Only a verified mapping proceeds to the archive skill's three-way confirmation. A candidate selection is not permission to modify files. Rows already in target history, unresolved rows, and rows outside the confirmed integration scope stay out of the mapping.

## Apply an approved mapping

After explicit **Update and archive** approval and archive-destination/pre-flight checks, edit only the exact approved suffixes on the approved completed rows. Never do a document-wide SHA substitution. Preserve every other byte of those rows, including titles, indices and checkbox marks; preserve all other plan content.

Before the move, write `reviews/archive-sha-repoint.md` with date, target remote/branch and snapshot OID, integration commit SHA/title, PR URL or user-confirmed association, evidence/change scope, explicit user decision, and a table of **row ID | old suffix (and resolved OID) | new SHA**. Include the affected-row total. Preserve an existing note by appending a new entry rather than overwriting it. This is provenance, not an implementation review and not review coverage.

The changed plan and this note must be staged at their destination paths in the same archive commit. Report the number of repointed rows in the final archive confirmation. Archive without repointing preserves the original SHAs; Cancel changes no files. Do not amend historical commits or modify an already archived plan.
