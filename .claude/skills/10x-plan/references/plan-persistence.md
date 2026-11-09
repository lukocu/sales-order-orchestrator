# Plan persistence across host modes

Apply this when questions and repository writes require different host modes, or when the user asks to save an already agreed plan. Otherwise use the ordinary writing steps in SKILL.md.

## Finish planning in a mode without repository writes

The deliverables still use the full Step 4 and Step 4.5 contracts in [plan-templates.md](plan-templates.md) (read when drafting or validating, reuse if already available): a plan with file-level Intent/Contract entries, per-phase Success Criteria and canonical unchecked Progress, plus its brief. A host's proposed-plan presentation is a container for those deliverables, not a substitute template. Follow higher-priority requirements for that presentation.

Resolve the actual project/worktree and active change path. At the initial skill read, retain the absolute path of the loaded SKILL.md and compute its SHA-256 from the file bytes with an available read-only tool. Resolve a relative discovery path against the actual working directory; never substitute a same-named global skill or infer the version from its picker label. If hashing is unavailable, report `unavailable` with the reason rather than inventing a digest. Keep the latest choices, superseded choices, agreed structure and scope in the conversation. Complete remaining decisions through the native question tool. Structure approval permits preparing the documents; it does not authorize product implementation.

At the end, proactively provide a handoff alongside the complete plan and brief:

```text
Plan and brief are ready in this conversation; repository files are not saved yet.
State: awaiting_persistence
Project: <actual absolute project/worktree path>
Skill: <actual loaded SKILL.md path>
Skill SHA-256: <digest of the loaded file bytes, or unavailable with reason>
Change: <change-id>
Targets: context/changes/<change-id>/{plan.md,plan-brief.md,change.md}
Latest decisions: <compact list including corrections and superseded choices>
Next: switch this same conversation to a mode allowing repository writes
(Default in Codex), then send:
$10x-plan <change-id> save
This saves the agreed documents only. Implementation has not been authorized.
```

Keep `Project`, `Skill` and `Skill SHA-256` as separate labeled fields; their values identify the actual project and loaded file, with absolute paths rather than `~` or relative paths. Adapt the surrounding explanation to the user's language. Say why the switch is needed before the user has to ask whether the plan was saved. Do not copy an implementation command to the clipboard or announce implementation readiness while persistence is pending. Do not change host configuration, start another agent to write, or use shell/temp files as a workaround for the mode restriction. The user or an authorized host controller performs the mode transition; never claim you changed it yourself.

## Resume persistence in a writable mode

Recognize the `save` suffix and equivalent natural language (for example, “switched to Default, save the plan”). A bare invocation for the same change immediately after this handoff also resumes persistence when the plan and decisions are still available. Route here before the native-question preflight and before complexity assessment.

1. Verify actual host mode and write permissions; a user's statement that they switched is not itself a capability change. If still read-only, retain `awaiting_persistence` and repeat the specific mode-switch/save instruction. Never attempt a forbidden write.
2. Recover the latest plan, brief, choices and corrections from this conversation or an explicitly supplied handoff. Do not re-ask settled questions or repeat research already completed. If context is unavailable, request the missing plan/handoff; do not reconstruct decisions from the change name. If a material decision is unresolved or newly changed, resolve only that delta using the required native question capability before saving.
3. Take **one** compact preflight: actual worktree/change identity, loaded skill path/digest already retained this turn, and a single `metadata-guard.mjs inspect` (with `--roadmap` when that file exists). Refuse archived targets. Probe optional paths only through that inspect result: a missing future plan is not evidence that the roadmap is absent. Do not `sed`/`cat` `change.md`, plan, brief or the skill files again unless inspect shows a hash that differs from the approved sources or a merge is required. Do not reload `SKILL.md`, this file, or `plan-templates.md` during save if they were already read this turn.
4. Materialize only missing or changed agreed content, preserving exact text and terminal newlines. This is a persistence transaction, not a return to discovery, plan composition or SKILL.md Step 5. Reuse templates already read; consult them only for an actual structural gap. Create change identity only if absent. An unchanged repeat updates neither metadata nor clipboard. An outline can be expanded to the established template, but missing product decisions require resolution first. Apply forward-only roadmap sync where relevant.
5. Use **one** verification pass over persisted bytes, then **one** `mark-planned`. Return compact evidence (hashes, section/Progress counts, helper JSON) rather than echoing documents or writing a second validator. Compare against the agreed write content. For changed decisions, derive each affected literal example from the new parameters and compare it with both documents. Check the one-to-one Success Criteria/Progress mapping in that same pass. New rows remain unchecked; existing execution rows and metadata remain intact. Do not run `inspect` again after a successful `mark-planned` unless the helper failed or disk bytes changed under you. If a write or check fails, report the actual partial state and retain incomplete status.

Keep a compact verified-save receipt in this conversation: absolute worktree/change,
loaded skill digest, fingerprints of plan/brief/change and any touched roadmap,
planning-input fingerprints, latest decisions and completed document/repository
checks. It is evidence from the completed verification, not a new required file or
a substitute for the complete documents. The fast path also requires the same
latest conversation decisions and scope, with no pending requested edits or
unresolved delta; unchanged disk bytes cannot cancel a newly agreed correction.
On an unchanged repeated save, compare current fingerprints with that receipt and report the existing state without
recomposing, rewriting or repeating unchanged checks. Required repository rules
still apply. If fingerprints differ, inspect only affected content and rerun the
affected checks; if the receipt or prior content is missing, validate the current
documents once. Hash equality alone never establishes first-time semantic validity.

For a settled `save`, skip complexity assessment, research delegation, provider browsing, SKILL.md Step 5, and product test/build commands unless changed evidence or repository instructions specifically require them. Batch independent local reads and mechanical checks into the single verification pass; do not invent a new validator or install dependencies merely to parse Markdown when existing tools suffice. Run applicable document/repository gates once and report their actual result. End with file links and a compact verification result; repeat full documents only when requested or a substantive revision needs review.

Save is idempotent: repeated invocation leaves already matching artifacts alone and never resets existing execution progress. If implementation has started, do not overwrite its plan or downgrade the change status to planned; report the existing state and handle any requested revision separately. Saving does not authorize implementation, commits, review, archive or deployment. Present the verified file links when persistence is complete; the normal implementation command is only a suggested next action.

### Reuse the metadata helper

When Node is available, use the bundled `../scripts/metadata-guard.mjs` (resolve from this reference or the actual loaded skill directory) for existing flat change frontmatter. Budget: **one** `inspect` in the compact preflight and **one** `mark-planned` after the verification pass. `inspect <change-dir> --roadmap <project>/context/foundation/roadmap.md` probes every target independently and returns hashes — that is the preflight read of those files. After verifying the saved plan and brief, run `mark-planned <change-dir> --expected-sha256 <inspected-change-hash> --date <actual-YYYY-MM-DD>`. It advances only `new`/`preparing`, preserves other bytes and later status, and leaves unchanged repeats untouched. It does not verify document semantics or update roadmap entries. Do not add extra `sha256sum` loops or `inspect` calls that repeat those hashes.

Do not rewrite existing `change.md` from a new template. If Node is unavailable or frontmatter syntax is unsupported, patch only the intended existing status/date lines with available tools and verify that identity, other fields and body remain intact. A stale-hash error requires rereading the changed file. The helper uses an optimistic fingerprint check and atomic replacement, not a lock shared with human editors. Create identity through normal `/10x-new` semantics only when genuinely absent. No new receipt file or dependency installation is required.

For restart recovery, prefer resuming the same conversation through the host. A fresh conversation requires the complete handoff/plan to be supplied or a previously persisted artifact; the skill cannot guarantee recovery of conversation-only text.
