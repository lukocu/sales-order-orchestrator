# Codex — hooks reference

Verified on: 2026-09-25

- https://developers.openai.com/codex/hooks (redirects to https://learn.chatgpt.com/docs/hooks; raw markdown at `https://learn.chatgpt.com/docs/hooks.md`)

If you can browse, re-check the `apply_patch` payload, the Stop output rules and the trust flow. Prefer the doc on conflict and note the discrepancy in the report. The doc warns that schemas on the `main` branch of `openai/codex` may be ahead of the release — the docs page is the reference.

## Detection signals

- `.codex/` directory: `hooks.json`, `config.toml`
- `.agents/.10x-cli-manifest.json` with `"tool": "codex"`
- `.agents/skills/` (the 10x-cli installs skills there for Codex) and `AGENTS.md` (course rule)
- This skill loaded from `.agents/skills/` (wins the tie-break)

`AGENTS.md` and `.agents/skills/` alone are weak evidence — many harnesses read `AGENTS.md`, and the 10x-cli also writes `.agents/skills/` into Claude Code repos.

## Config locations

- `<repo>/.codex/hooks.json` or `[hooks]` in `<repo>/.codex/config.toml` — project, loads only when the project `.codex/` layer is trusted
- `~/.codex/hooks.json` or `[hooks]` in `~/.codex/config.toml` — user
- Managed hooks (`requirements.toml`, MDM) — trusted by policy

Layers merge; higher-precedence layers do not replace lower ones. JSON shape (same nesting as Claude Code):

```json
{
  "hooks": {
    "PostToolUse": [{ "matcher": "apply_patch", "hooks": [{ "type": "command", "command": "...", "timeout": 30 }] }]
  }
}
```

`matcher` is a regex on the tool name (`"*"`, `""` or omitted = everything). Handlers: **`command`** and `mcp_tool` run; `prompt` and `agent` are parsed but **skipped**. Extra fields: `statusMessage`, `commandWindows` (Windows-only command override; `command_windows` in TOML), `async: true` (background, cannot block).

## Events that matter here

12 events. Per edit: **`PostToolUse`** on the edit tool. End of turn: **`Stop`**.

## Payload

Common: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`, `permission_mode`. `PostToolUse` adds `turn_id`, `tool_name`, `tool_use_id`, `tool_input`, `tool_response`.

**File edits arrive as `apply_patch`, not as `Write`/`Edit` with a path.** `tool_name` is always `"apply_patch"` (the matcher may also say `Edit` or `Write`). There is **no `tool_input.file_path`**: `tool_input.command` holds the raw patch text, and the edited paths must be parsed from its file headers (`*** Update File: <path>`, `*** Add File: <path>`, `*** Move to: <path>` for a rename — the header format is the patch format, not spelled out in the hooks doc; verify on the first run). Paths are relative to the session `cwd`. One patch can touch several files.

`Stop` includes **`stop_hook_active`** ("whether this turn was already continued by `Stop`") and `last_assistant_message`.

## Signal channel — what reaches the agent

- **`PostToolUse`:** exit `2` with the feedback on **stderr**, or exit `0` with JSON `{"decision": "block", "reason": "..."}` (replaces the tool result with the feedback; the edit is not undone) and/or `hookSpecificOutput.additionalContext` (extra developer context). **Plain stdout is ignored.**
- **`Stop`:** exit `2` with the continuation reason on stderr, or JSON `{"decision": "block", "reason": "..."}`. The reason becomes a new continuation prompt. When `Stop` exits `0` it **expects JSON on stdout** — plain text is invalid, so print `{}` (or nothing) on success.
- Model-visible hook output is capped at about 2,500 tokens (`additionalContextLimit`); longer output is saved to disk and previewed head-and-tail.
- No documented Stop loop cap — the script must guard with `stop_hook_active`.

## Timeouts

`timeout` in **seconds**, default 600 for most events.

## Trust and approval

Codex records trust against the hook definition's **hash**. New or changed non-managed hooks — project **and** user — are marked for review and **skipped until trusted**. After writing or editing hooks the user must run **`/hooks`** in the Codex CLI, review and trust them. Every later change needs re-approval. A hook that "does nothing" is usually an untrusted one. (`--dangerously-bypass-hook-trust` exists for one-off runs; do not recommend it.)

## Paths, shell, Windows

- Commands run with the session `cwd` via `$SHELL -lc` (`%COMSPEC% /C` on Windows). No project-dir variable is documented; resolve the repo root with `$(git rev-parse --show-toplevel)` because Codex may start in a subdirectory.
- Windows: `%COMSPEC% /C` does not expand `$(git rev-parse …)`, so `command` cannot find the script there. Add `commandWindows` that resolves the root itself, e.g. `"commandWindows": "powershell -NoProfile -Command \"& bash (Join-Path (git rev-parse --show-toplevel) '.codex/hooks/lint-edited-file.sh')\""`. The bash + `jq` scripts need Git Bash and `jq` on PATH; otherwise port them to Node (`node <root>/.codex/hooks/lint-edited-file.mjs`) and point `commandWindows` at that. Prove it on the Windows machine.

## Gotchas

- A script that reads `tool_input.file_path` gets nothing and silently passes every edit.
- `eslint --fix` rewrites the file the agent just patched; drop it if the agent's next patch fails on the changed file. Derive the `case` extension list from the lint config (`*.astro`, `*.vue`, `*.svelte`).
- Typecheck: run a framework's type-generation step first (`astro sync` before `tsc`), and run the Stop script once on the untouched tree — if it is red there, scope it (project tsconfig, or diagnostics in changed files, see `anthropic.md`) or report a blocker. Keep output plain: `NO_COLOR=1 FORCE_COLOR=0`, `tsc --pretty false`, `grep --color=never`.
- Matching hooks run concurrently; keep per-edit hooks independent.
- Hooks are a guardrail, not an enforcement boundary: some tool paths skip the hook path.

## Minimal example

`.codex/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "apply_patch",
        "hooks": [
          {
            "type": "command",
            "command": "\"$(git rev-parse --show-toplevel)/.codex/hooks/lint-edited-file.sh\"",
            "timeout": 30
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$(git rev-parse --show-toplevel)/.codex/hooks/end-of-turn.sh\"",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

`.codex/hooks/lint-edited-file.sh`:

<!-- proof: lint-edited-file.sh -->

```bash
#!/usr/bin/env bash
# PostToolUse (apply_patch): lint every JS/TS file named in the patch.
export NO_COLOR=1 FORCE_COLOR=0
INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -n "$CWD" ] && cd "$CWD" 2>/dev/null

PATCH=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
FILES=$(printf '%s\n' "$PATCH" | sed -n -E 's/^\*\*\* (Update File|Add File|Move to): (.*)$/\2/p')

FAILED=""
while IFS= read -r FILE; do
  case "$FILE" in
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) ;;  # derive from the lint config (.astro, .vue, …)
    *) continue ;;
  esac
  [ -f "$FILE" ] || continue
  if ! OUTPUT=$(npx eslint --fix --quiet "$FILE" 2>&1); then
    FAILED="$FAILED
ESLint reported errors in $FILE:
$OUTPUT"
  fi
done <<< "$FILES"

if [ -n "$FAILED" ]; then
  echo "$FAILED" >&2
  exit 2
fi
exit 0
```

`.codex/hooks/end-of-turn.sh`:

<!-- proof: end-of-turn.sh -->

```bash
#!/usr/bin/env bash
# Stop: sweep everything this turn changed, send the agent back once.
export NO_COLOR=1 FORCE_COLOR=0
INPUT=$(cat)
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 0

if [ "$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ]; then
  echo '{}'
  exit 0
fi

# Changed and new files. Nothing changed (a Q&A turn): nothing to check.
CHANGED=$({ git diff --name-only HEAD; git ls-files -o --exclude-standard; } 2>/dev/null | sort -u)
[ -n "$CHANGED" ] || { echo '{}'; exit 0; }

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
echo '{}'
exit 0
```

Then tell the user: run `/hooks` in Codex, review and trust both hooks, and re-trust after every change.

Extra proof cases for Codex (on top of SKILL.md Step 7): a non-patch payload (`tool_input` without `command`, or a patch with no file headers) → exit 0; a multi-file patch with the error in the second file → exit 2 naming that file; a `*** Move to:` rename onto a broken file → exit 2; `cwd` set to a subdirectory with paths relative to it → the file is still found.

Manual proof:

```bash
jq -nc --arg c $'*** Begin Patch\n*** Update File: src/lib/auth.ts\n*** End Patch' \
  '{tool_name:"apply_patch",tool_input:{command:$c},cwd:env.PWD}' | .codex/hooks/lint-edited-file.sh; echo "exit: $?"
echo '{"stop_hook_active":true}' | .codex/hooks/end-of-turn.sh; echo "exit: $?"   # expect 0
```
