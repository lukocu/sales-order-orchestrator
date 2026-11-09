# Cursor — hooks reference

Verified on: 2026-09-25

- https://cursor.com/docs/hooks
- https://cursor.com/docs/reference/third-party-hooks (import of Claude Code hooks)

If you can browse, re-check the `postToolUse` payload for file edits, the `additional_context` / `followup_message` spelling and the import rules. Prefer the doc on conflict and note the discrepancy in the report.

## Detection signals

- `.cursor/` directory: `hooks.json`, `rules/`, `skills/`
- `.cursor/rules/10x-course.mdc` (the 10x-cli writes the course rule there for Cursor)
- `.cursor/.10x-cli-manifest.json` with `"tool": "cursor"`
- This skill loaded from `.cursor/skills/` (wins the tie-break)
- `.claude/settings*.json` with hooks in a Cursor repo — Cursor imports them (see "Double registration")

## Config locations

Priority, highest first: Enterprise (`/Library/Application Support/Cursor/hooks.json`, `/etc/cursor/hooks.json`, `C:\ProgramData\Cursor\hooks.json`) → Team (dashboard) → **project `.cursor/hooks.json`** → user `~/.cursor/hooks.json` → imported Claude Code hooks. All matching hooks from every source run. Cursor watches the files and reloads them.

Shape — a flat list per event, `version: 1` required:

```json
{
  "version": 1,
  "hooks": {
    "postToolUse": [{ "command": ".cursor/hooks/lint-edited-file.sh", "matcher": "Write", "timeout": 30 }]
  }
}
```

Per-hook fields: `command`, `type` (`"command"` | `"prompt"`), `timeout`, `matcher` (regex; `""`/`"*"` match everything), `loop_limit`, `failClosed` (when `true`, a crash, timeout or non-zero exit blocks the action instead of failing open).

Project hooks run **from the project root**: use `.cursor/hooks/script.sh`, not `./hooks/script.sh`. User hooks run from `~/.cursor/`.

## Events that matter here

18 agent events. The two that can talk back to the agent:

- **Per edit: `postToolUse`** with `matcher: "Write"` (file edits appear as the `Write` tool; others: `Shell`, `Read`, `Grep`, `Delete`, `Task`, `MCP:<tool>`).
- **End of turn: `stop`** (matched against `Stop`).

`afterFileEdit` has a convenient payload (`file_path`, `edits`) but **no output schema** — it is for formatters and accounting. Nothing it prints reaches the agent. Do not use it for feedback.

## Payload

Common fields: `conversation_id`, `generation_id`, `hook_event_name`, `workspace_roots`, `cursor_version`, `transcript_path`…

- `postToolUse`: `tool_name`, `tool_input`, `tool_output` (JSON-stringified), `tool_use_id`, `cwd`, `duration`. **The docs do not state the path field inside `tool_input` for `Write`.** Read `tool_input.file_path` and fall back to `tool_input.path` / `tool_input.target_file`; confirm the real field in the Hooks output channel on the first run.
- `stop`: `status` (`"completed"` | `"aborted"` | `"error"`) and `loop_count` (how many automatic follow-ups this hook already triggered, starts at 0). There is no `stop_hook_active`; `loop_count` is the equivalent.

## Signal channel — what reaches the agent

Exit `0` and print JSON on stdout:

| Event         | Field                | Effect                                                                     |
| ------------- | -------------------- | -------------------------------------------------------------------------- |
| `postToolUse` | `additional_context` | Injected into the conversation after the tool result                       |
| `stop`        | `followup_message`   | Submitted automatically as the next user message — the agent keeps working |

Exit `2` blocks the action (equivalent to `permission: "deny"`) for permission hooks; its effect on `postToolUse`/`stop` is not documented — do not rely on it. Other non-zero exits fail open unless `failClosed` is set.

Stop loop limit: `loop_limit`, default **5** follow-ups per script for Cursor hooks and **unlimited (`null`)** for imported Claude Code hooks. Set `"loop_limit": 1` and also check `loop_count` in the script.

## Timeouts

`timeout` is in **seconds**.

## Trust, environment, Windows

- Project hooks run only in a **trusted workspace**; no per-hook approval.
- Env: `CURSOR_PROJECT_DIR`, `CURSOR_VERSION` (always set), and `CLAUDE_PROJECT_DIR` as an alias of the project dir.
- Cloud agents run project `.cursor/hooks.json` command hooks only, not user hooks.
- Windows: the docs give no shell guidance beyond the enterprise path. Test the command in the shell Cursor uses on that machine, or generate a Node script (`node .cursor/hooks/lint-edited-file.mjs`).
- Debug: the **Hooks** output channel and the Hooks tab in Customize.

## Double registration (`.claude` import)

With **Settings → Agents → Third-Party Imports → "Include Third-Party Plugins, Skills, and Other Configs"** (on by default), Cursor loads hooks from `.claude/settings.local.json`, `.claude/settings.json` and `~/.claude/settings.json`. Mapping: `PostToolUse` → `postToolUse`, `Stop` → `stop`; tools `Edit`/`Write` → `Write`, `Bash` → `Shell`. A Claude Stop `{"decision":"block","reason":…}` becomes a follow-up; whether a Claude-style exit 2 + stderr reaches Cursor's agent is **not stated**.

So a repo used with both Claude Code and Cursor that has hooks in `.claude/settings.json` already runs them in Cursor. Never add the same check to `.cursor/hooks.json` without choosing one registration per harness:

1. **Preferred:** keep the Claude scripts for Claude Code, add Cursor-native hooks (below), and make the Claude scripts exit early under Cursor with `[ -n "${CURSOR_VERSION:-}" ] && exit 0` as their first line. Each harness then runs exactly one copy in its own protocol.
2. Or rely on the import only — then prove in Cursor that the agent actually receives the message; the Claude Stop script must guard on `loop_count` too, since the import has no loop limit.

Report which option you chose.

## Gotchas

- `afterFileEdit` looks like the natural per-edit event but cannot inform the agent.
- Matchers are a flat `matcher` field on each hook, not Claude's nested `matcher` + `hooks`.
- Paths relative to the project root; `./hooks/…` fails.
- Only one JSON object on stdout; keep linter output inside the JSON string, never loose on stdout.
- `eslint --fix` rewrites the file the agent just edited; drop `--fix` if the agent's next edit trips over the changed file. Derive the `case` extension list from the lint config (`*.astro`, `*.vue`, `*.svelte` when their plugins are configured).
- Typecheck: frameworks with generated types need their sync step first (`tsc` fails on `astro:*` modules until `astro sync` has generated `.astro/`; `astro check` syncs itself). Run the stop script once on the untouched tree; if it is red there, scope it (project tsconfig, or diagnostics in changed files — see the commented variant in `anthropic.md`'s `end-of-turn.sh`) or report a blocker.
- Plain output: the scripts set `NO_COLOR=1 FORCE_COLOR=0` and `tsc --pretty false`; use `grep --color=never` in any filter (the user's env may set `GREP_OPTIONS`).

## Minimal example

`.cursor/hooks.json` (merge into existing `hooks`):

```json
{
  "version": 1,
  "hooks": {
    "postToolUse": [{ "command": ".cursor/hooks/lint-edited-file.sh", "matcher": "Write", "timeout": 30 }],
    "stop": [{ "command": ".cursor/hooks/end-of-turn.sh", "timeout": 120, "loop_limit": 1 }]
  }
}
```

`.cursor/hooks/lint-edited-file.sh`:

<!-- proof: lint-edited-file.sh -->

```bash
#!/usr/bin/env bash
# postToolUse (Write): lint the edited file; errors go back as additional_context.
cd "${CURSOR_PROJECT_DIR:-.}" || exit 0
export NO_COLOR=1 FORCE_COLOR=0

FILE=$(jq -r '.tool_input.file_path // .tool_input.path // .tool_input.target_file // empty' 2>/dev/null)

case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) ;;
  *) exit 0 ;;
esac
[ -f "$FILE" ] || exit 0

if ! OUTPUT=$(npx eslint --fix --quiet "$FILE" 2>&1); then
  jq -n --arg msg "ESLint reported errors in $FILE:
$OUTPUT" '{additional_context: $msg}'
fi
exit 0
```

`.cursor/hooks/end-of-turn.sh`:

<!-- proof: end-of-turn.sh -->

```bash
#!/usr/bin/env bash
# stop: sweep everything this turn changed, send the agent back once.
cd "${CURSOR_PROJECT_DIR:-.}" || exit 0
export NO_COLOR=1 FORCE_COLOR=0

INPUT=$(cat)
STATUS=$(printf '%s' "$INPUT" | jq -r '.status // "completed"' 2>/dev/null)
LOOPS=$(printf '%s' "$INPUT" | jq -r '.loop_count // 0' 2>/dev/null)

# Only after a normal finish, and only the first time.
if [ "$STATUS" != "completed" ] || [ "${LOOPS:-0}" != "0" ]; then
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
  jq -n --arg msg "Fix these before you finish:$REPORT" '{followup_message: $msg}'
fi
exit 0
```

Manual proof (expect JSON with `additional_context` / `followup_message` on the broken file, nothing on a clean one):

```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"'"$PWD"'/src/lib/auth.ts"}}' | .cursor/hooks/lint-edited-file.sh; echo "exit: $?"
echo '{"status":"completed","loop_count":0}' | .cursor/hooks/end-of-turn.sh; echo "exit: $?"
echo '{"status":"completed","loop_count":1}' | .cursor/hooks/end-of-turn.sh; echo "exit: $?"   # expect no output
```
