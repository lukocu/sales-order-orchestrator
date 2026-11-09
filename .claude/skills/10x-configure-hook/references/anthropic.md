# Claude Code — hooks reference

Verified on: 2026-09-25

- https://code.claude.com/docs/en/hooks (reference; raw markdown at `hooks.md`)
- https://code.claude.com/docs/en/hooks-guide

If you can browse, re-check the payload field, exit-code table and timeout defaults there. Prefer the doc on conflict and note the discrepancy in the report.

## Detection signals

- `.claude/` directory: `settings.json`, `settings.local.json`, `skills/`, `hooks/`
- `CLAUDE.md` at the repo root (the 10x-cli writes the course rule there for Claude Code)
- `.claude/.10x-cli-manifest.json` with `"tool": "claude-code"`
- This skill loaded from `.claude/skills/` (wins the tie-break)

`.agents/skills/` and `AGENTS.md` are weak evidence: the 10x-cli writes `.agents/skills/` into Claude Code repos too.

## Config locations

| File                                                     | Scope                                         |
| -------------------------------------------------------- | --------------------------------------------- |
| `~/.claude/settings.json`                                | All your projects                             |
| `.claude/settings.json`                                  | This project, committed with `.claude/hooks/` |
| `.claude/settings.local.json`                            | This project, local only (gitignored)         |
| Managed policy settings                                  | Organisation, admin-controlled                |
| Plugin `hooks/hooks.json`, skill or subagent frontmatter | While the plugin / skill / subagent is active |

Hooks from different levels **merge**; they do not replace each other. Shape:

```json
{
  "hooks": {
    "PostToolUse": [{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "...", "timeout": 30 }] }]
  }
}
```

## Events that matter here

- **Per edit:** `PostToolUse` with matcher `Write|Edit` (regex on the tool name; `Edit.*` also catches `NotebookEdit`). There is no `MultiEdit` tool. `PostToolBatch` fires once after a batch of parallel tool calls (no matcher). A `Bash` command that rewrites a file does **not** trigger a `Write|Edit` hook.
- **End of turn:** `Stop` (no matcher). The docs list 33 events in total.

## Payload

JSON on stdin. `PostToolUse` fields include `session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_input`, `tool_response`. For `Write`/`Edit`, the edited path is **`tool_input.file_path`**, always absolute (on Windows with backslashes, even under Git Bash).

`Stop` includes **`stop_hook_active`** — `true` when Claude is already continuing because a Stop hook blocked.

## Signal channel — what reaches the agent

| Exit code         | PostToolUse                                                                               | Stop                                                           |
| ----------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `0`               | Success. stdout goes to the debug log only; stderr is never seen by Claude                | Agent stops normally                                           |
| `2`               | **stderr is shown to Claude** next to the tool result (the edit already happened)         | **Agent does not stop**; stderr is the reason it keeps working |
| other (incl. `1`) | Non-blocking error: the user sees "hook error" in the transcript, **Claude sees nothing** | Same                                                           |

Most linters and test runners exit `1` and print to stdout, so a raw `npx eslint .` hook reaches nobody. Scripts must redirect output to stderr (`>&2`) and turn any failure into `exit 2`.

JSON alternative (exit 0, stdout): `{"decision": "block", "reason": "..."}` or `hookSpecificOutput.additionalContext`. stderr + exit 2 is enough for linter and test output.

Stop block cap: after **8** consecutive blocks Claude Code ends the turn anyway (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` raises it). Use the `stop_hook_active` guard instead of relying on the cap.

## Timeouts

`timeout` is in **seconds**. Defaults: 600 for `command`/`http`/`mcp_tool`, 30 for `prompt`, 60 for `agent`. `10000` means almost three hours, not ten seconds.

## Paths, shell, Windows

- `$CLAUDE_PROJECT_DIR` is the project root where the session started (in worktrees it keeps pointing at the main checkout). Reference scripts as `"$CLAUDE_PROJECT_DIR"/.claude/hooks/<script>.sh`.
- Commands run with `sh -c` on macOS/Linux and Git Bash on Windows. The per-hook `shell` field accepts `"bash"` or `"powershell"` (default PowerShell on Windows without Git Bash). Without Git Bash or `jq`, generate a Node script instead.

## Trust and debugging

- No approval step: hooks in settings files run once the session loads them. Restart the session after editing settings.
- `/hooks` — read-only list of loaded hooks with their source file. Missing? Check the JSON (a trailing comma breaks it).
- `claude --debug-file /tmp/claude.log` (or `claude --debug`, log at `~/.claude/debug/<session-id>.txt`) shows which hooks matched, their exit code and output. Ctrl+O shows hook output in the transcript.

## Gotchas

- `eslint --fix .` per edit: slow, rewrites files the agent did not touch, reports old errors as noise.
- `eslint --fix "$FILE"` rewrites the file the agent just edited, so its next `Edit` can fail with "file modified since read" and cost a re-read. Drop `--fix` (`npx eslint --quiet "$FILE"`) to report only and let the agent fix.
- The `case` extension list is an example: derive it from the lint config (add `*.astro` with `eslint-plugin-astro`, `*.vue`, `*.svelte` likewise).
- Generated types: `tsc --noEmit` fails on `astro:*` modules until `astro sync` has generated `.astro/`; `astro check` syncs itself but is slower. Any framework with generated types needs its sync step before the typecheck.
- Red baseline: run the Stop script once on the untouched tree. If it blocks there, fix the prerequisite or scope it (the commented variant in `end-of-turn.sh`: a project tsconfig, or diagnostics in changed files only).
- Plain output: hooks inherit the user's shell env (`GREP_OPTIONS=--color=always`, `FORCE_COLOR`); the scripts set `NO_COLOR=1 FORCE_COLOR=0`, `tsc --pretty false` and `grep --color=never`.
- Whole-project `tsc` per edit: mid-refactor type errors the agent is about to fix anyway. Move it to `Stop`.
- `Stop` fires at the end of every response, including pure Q&A. The end-of-turn script exits early when nothing changed.
- A file rewritten through `Bash` (`cat > f <<EOF`, `sed -i`) never reaches a `Write|Edit` hook, and agents do this. The end-of-turn script lints and tests every changed file from `git diff`, so those edits are still checked once per turn.
- `vitest related <file> --run` exits 0 when no test depends on the file (also for `.md`, a deleted file or an empty path); editing `package.json` runs the whole suite. Jest needs `--findRelatedTests <file> --passWithNoTests`. Vitest detects Claude Code on its own (`CLAUDECODE`), no `AI_AGENT=1` needed.
- Cursor imports `.claude/settings*.json` hooks (on by default) — see `cursor.md` before adding Cursor-native hooks to the same repo. The Stop script below also honours Cursor's `loop_count` so it stays safe when imported.

## Minimal example

`.claude/settings.json` (merge into existing `hooks`, do not replace them):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/lint-edited-file.sh", "timeout": 30 },
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/related-tests.sh", "timeout": 60 }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/end-of-turn.sh", "timeout": 120 }
        ]
      }
    ]
  }
}
```

`.claude/hooks/lint-edited-file.sh` — lint only the edited file:

<!-- proof: lint-edited-file.sh -->

```bash
#!/usr/bin/env bash
# PostToolUse (Write|Edit): lint the file the agent just edited.
# Exit 2 + stderr is the only combination Claude sees.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
export NO_COLOR=1 FORCE_COLOR=0

FILE=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Only files the linter covers (derive the list from the lint config) that still exist.
case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) ;;
  *) exit 0 ;;
esac
[ -f "$FILE" ] || exit 0

if ! OUTPUT=$(npx eslint --quiet "$FILE" 2>&1); then
  echo "ESLint reported errors in $FILE:" >&2
  echo "$OUTPUT" >&2
  exit 2
fi
exit 0
```

`.claude/hooks/end-of-turn.sh` — at end of turn: lint and related tests for every changed file, then a whole-project typecheck; one retry:

<!-- proof: end-of-turn.sh -->

```bash
#!/usr/bin/env bash
# Stop: sweep everything this turn changed before the agent finishes, one retry.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
export NO_COLOR=1 FORCE_COLOR=0

INPUT=$(cat)

# Already sent back once by this hook: let it finish. The commit gate catches the rest.
# (loop_count covers Cursor, which imports this hook from .claude/settings.json.)
ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)
LOOPS=$(printf '%s' "$INPUT" | jq -r '.loop_count // 0' 2>/dev/null)
if [ "$ACTIVE" = "true" ] || [ "${LOOPS:-0}" != "0" ]; then
  exit 0
fi

# Changed and new files. Nothing changed (a Q&A turn): nothing to check.
CHANGED=$({ git diff --name-only HEAD; git ls-files -o --exclude-standard; } 2>/dev/null | sort -u)
[ -n "$CHANGED" ] || exit 0

# Changed files the linter covers (derive the list from the lint config) that still exist.
# This also catches files rewritten through a shell command, which never reach a per-edit hook.
FILES=()
while IFS= read -r f; do
  case "$f" in *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) [ -f "$f" ] && FILES+=("$f") ;; esac
done <<EOF
$CHANGED
EOF

REPORT=""
if [ "${#FILES[@]}" -gt 0 ]; then
  OUT=$(npx eslint --quiet "${FILES[@]}" 2>&1) || REPORT="$REPORT
ESLint errors in changed files:
$OUT
"
  # Whole unit suite runs in seconds? Use `npx vitest run` instead: it also catches
  # a red test in a module this turn only imported.
  OUT=$(npx vitest related "${FILES[@]}" --run 2>&1) || REPORT="$REPORT
Tests related to changed files fail:
$OUT
"
fi

# Generated types are gitignored, so regenerate them in the hook, not once by hand:
# [ -f .astro/types.d.ts ] || npx astro sync >/dev/null 2>&1
if ! OUT=$(npx tsc --noEmit --pretty false 2>&1); then
  # Red on the untouched tree? Scope it: `-p <app tsconfig>`, drop a nested package
  # pulled in by `**/*`:
  # OUT=$(printf '%s\n' "$OUT" | grep --color=never -v '^packages/')
  # or keep only changed files:
  # OUT=$(printf '%s\n' "$OUT" | grep --color=never -F "$CHANGED")
  [ -n "$OUT" ] && REPORT="$REPORT
Typecheck fails:
$OUT
"
fi

if [ -n "$REPORT" ]; then
  echo "Fix these before you finish:$REPORT" >&2
  exit 2
fi
exit 0
```

`.claude/hooks/related-tests.sh` — tests that depend on the edited file (optional, per edit):

<!-- proof: related-tests.sh -->

```bash
#!/usr/bin/env bash
# PostToolUse (Write|Edit): run the tests related to the edited file.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
export NO_COLOR=1 FORCE_COLOR=0

FILE=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)

case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx) ;;
  *) exit 0 ;;
esac
[ -f "$FILE" ] || exit 0

if ! OUTPUT=$(npx vitest related "$FILE" --run 2>&1); then
  echo "Tests related to $FILE fail:" >&2
  echo "$OUTPUT" >&2
  exit 2
fi
exit 0
```

`chmod +x .claude/hooks/*.sh`. Manual proof:

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"'"$PWD"'/src/lib/auth.ts"}}' | .claude/hooks/lint-edited-file.sh; echo "exit: $?"
echo '{"stop_hook_active":false}' | .claude/hooks/end-of-turn.sh; echo "exit: $?"
echo '{"stop_hook_active":true}'  | .claude/hooks/end-of-turn.sh; echo "exit: $?"   # expect 0
```
