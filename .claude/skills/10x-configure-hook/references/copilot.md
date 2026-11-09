# GitHub Copilot — hooks reference

Verified on: 2026-09-25

- https://docs.github.com/en/copilot/reference/hooks-reference (Copilot CLI and cloud agent)
- https://code.visualstudio.com/docs/agent-customization/hooks (VS Code; the Local hooks schema is at https://code.visualstudio.com/docs/agents/reference/hooks-reference)

Copilot has **three runtimes with different schemas**. Find out which one the user runs (CLI, VS Code agent mode, cloud coding agent) before generating anything; ask if the repo does not show it. If you can browse, re-check the payload and output field names for that runtime — they are the part most likely to have moved. Prefer the doc on conflict and note the discrepancy in the report.

## Detection signals

- `.github/hooks/*.json`
- `.github/skills/` (the 10x-cli installs skills there for Copilot) and `.github/copilot-instructions.md` (course rule)
- `.github/copilot/settings.json`, `.vscode/settings.json` with `chat.hookFilesLocations` / `chat.useClaudeHooks`
- `.github/.10x-cli-manifest.json` with `"tool": "copilot"`
- This skill loaded from `.github/skills/` (wins the tie-break)

## Runtimes at a glance

|                | Copilot CLI                                                                                                                    | VS Code agent mode ("Local" harness)                                                                                                                                                                     | Cloud coding agent                                                   |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Config         | `.github/hooks/*.json`, `~/.copilot/hooks/`, `.github/copilot/settings*.json`; also reads `.claude/settings*.json` in the repo | `.github/hooks/*.json`, `~/.copilot/hooks/*.json`, `.agent.md` frontmatter; `.claude/settings*.json` only with `chat.useClaudeHooks` (off by default); `chat.hookFilesLocations` adds/disables locations | `.github/hooks/*.json` **on the default branch**; no `settings.json` |
| Events         | camelCase: `postToolUse`, `agentStop`, … (PascalCase names also accepted)                                                      | 8 PascalCase: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `SubagentStart`, `SubagentStop`, `Stop`                                                                     | CLI set; most events fire                                            |
| Matchers       | Regex on `toolName` (`^(?:PATTERN)$`); Claude matcher semantics documented only for `PreToolUse`/`PermissionRequest`           | **Ignored** for Claude-format files — every command for the event runs                                                                                                                                   | As CLI                                                               |
| Command fields | `bash`, `powershell`, `command` (cross-platform fallback), `cwd`, `env`                                                        | `command`, `windows` / `linux` / `osx`, `cwd`, `env`                                                                                                                                                     | Only `bash` (or `command`); `powershell` ignored                     |
| Timeout        | `timeoutSec` (alias `timeout`), **seconds**, default 30                                                                        | `timeout`, **seconds**, default 30                                                                                                                                                                       | As CLI                                                               |

VS Code sessions that run on the **Copilot harness** (Agent Host) use the CLI implementation, not the Local schema.

## Payload

- **CLI, camelCase events:** `sessionId`, `timestamp`, `cwd`, `toolName`, `toolArgs` (may arrive as a **JSON string**), `toolResult`. PascalCase events get snake_case fields: `tool_name`, `tool_input`, `tool_result`. Edit tools: `edit`, `create` (Claude-name mapping: `edit`/`str_replace_editor`/`apply_patch` → `Edit`, `create` → `Write`).
- **VS Code Local:** `tool_name`, `tool_input`, `tool_use_id`, `tool_response`, plus `session_id`, `hook_event_name`, `cwd`, `timestamp`. The docs say to read the exact tool names from the agent debug logs and not to copy them from another harness.
- **The path field inside the tool arguments is not documented** for any runtime. Read `file_path`, `filePath` and `path` from `tool_input` or the parsed `toolArgs`, and confirm on the first run.
- `Stop` / `agentStop` includes **`stop_hook_active`** in the CLI and in VS Code Local.

## Signal channel — what reaches the agent

|               | Per edit                                                                                                                                                                        | End of turn                                                                                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CLI / cloud   | Exit `0` + JSON `{"additionalContext": "..."}` — appended to the tool result, capped at 10 KB. **Exit `2` is only a warning** for `postToolUse`; other non-zero exits fail open | `agentStop`: exit `0` + `{"decision": "block", "reason": "..."}` forces another turn with `reason` as the prompt; the CLI overrides the hook after 8 consecutive blocks |
| VS Code Local | Exit `2` + stderr is shown to the model, or exit `0` + `hookSpecificOutput.additionalContext`                                                                                   | `Stop`: `{"hookSpecificOutput": {"hookEventName": "Stop", "decision": "block", "reason": "..."}}` (nested, unlike CLI)                                                  |

Only one JSON object may be printed on stdout. The example scripts below print one object that carries both the CLI field and the VS Code field, so one script serves both runtimes. The docs do not say that either runtime tolerates the other's extra fields — prove it in the runtime you configure.

## Trust and disabling

- VS Code: `chat.useHooks` (on by default); workspace hook files are subject to **Workspace Trust**; the org policy `ChatHooks` disables Local hooks.
- CLI / cloud: `disableAllHooks` in a hooks file skips every hook; policy hooks (`/etc/github-copilot/policy.d/*.json`) cannot be disabled. Cloud runs are non-interactive with permissions pre-granted.

## Windows

CLI: `powershell` field (PowerShell 7+ on PATH). VS Code: `windows` field, chosen by the extension-host platform (can differ from the UI in Remote windows). Or generate a Node script.

## Gotchas

- A Claude Code hook copied as-is: VS Code ignores its matcher (runs on every tool), the tool names and payload fields differ, and in the CLI an exit 2 on `postToolUse` does not reach the model.
- Tool names differ per runtime: filter by file type inside the script instead of trusting matchers.
- Cloud agent reads hooks only from the default branch.
- Double registration: the CLI reads `.claude/settings*.json`, VS Code does with `chat.useClaudeHooks`. If those files hold hooks, make the Claude scripts exit early under Copilot or rely on one registration only, and report the choice.
- VS Code ignores matchers, so a `PostToolUse` hook also fires after read tools (`read_file`, search…): the lint script skips read-only tool names. Multi-file edits nest paths (`replacements[].filePath`), so it collects every `file_path` / `filePath` / `path` recursively.
- `eslint --fix` rewrites the file the agent just edited; drop it if that disturbs the agent's next edit. Derive the `case` extension list from the lint config (`*.astro`, `*.vue`, `*.svelte`).
- Typecheck: run a framework's type-generation step first (`astro sync` before `tsc`), and run the stop script once on the untouched tree — if it is red there, scope it (project tsconfig, or diagnostics in changed files, see `anthropic.md`) or report a blocker. Keep output plain: `NO_COLOR=1 FORCE_COLOR=0`, `tsc --pretty false`, `grep --color=never`.

## Minimal example

`.github/hooks/quality.json` (CLI format; VS Code maps lower-camel-case events from this format):

```json
{
  "version": 1,
  "hooks": {
    "postToolUse": [{ "type": "command", "command": ".github/hooks/lint-edited-file.sh", "timeout": 30 }],
    "agentStop": [{ "type": "command", "command": ".github/hooks/end-of-turn.sh", "timeout": 120 }]
  }
}
```

`.github/hooks/lint-edited-file.sh`:

<!-- proof: lint-edited-file.sh -->

```bash
#!/usr/bin/env bash
# postToolUse / PostToolUse: lint the edited file(s); errors go back as additionalContext.
export NO_COLOR=1 FORCE_COLOR=0
INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -n "$CWD" ] && cd "$CWD" 2>/dev/null

# VS Code ignores matchers: skip read-only tools.
TOOL=$(printf '%s' "$INPUT" | jq -r '(.tool_name // .toolName // "") | ascii_downcase' 2>/dev/null)
case "$TOOL" in
  *read*|view|*search*|grep*|list*|glob*|fetch*|get_*) exit 0 ;;
esac

# toolArgs may be a JSON string; multi-file edits nest paths (replacements[].filePath).
FILES=$(printf '%s' "$INPUT" | jq -r '
  ( .tool_input
    // ((.toolArgs // null) | if type == "string" then (fromjson? // null) else . end)
    // {} )
  | [.. | objects | (.file_path // .filePath // .path // empty) | strings] | unique | .[]
' 2>/dev/null)

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
  jq -n --arg msg "$FAILED" '{additionalContext: $msg, hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $msg}}'
fi
exit 0
```

`.github/hooks/end-of-turn.sh`:

<!-- proof: end-of-turn.sh -->

```bash
#!/usr/bin/env bash
# agentStop / Stop: sweep everything this turn changed, send the agent back once.
export NO_COLOR=1 FORCE_COLOR=0
INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -n "$CWD" ] && cd "$CWD" 2>/dev/null
if [ "$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ]; then
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
  jq -n --arg msg "Fix these before you finish:$REPORT" '{decision: "block", reason: $msg, hookSpecificOutput: {hookEventName: "Stop", decision: "block", reason: $msg}}'
fi
exit 0
```

Manual proof:

```bash
jq -nc --arg p "$PWD/src/lib/auth.ts" '{toolName:"edit",toolArgs:({path:$p}|tojson)}' | .github/hooks/lint-edited-file.sh; echo "exit: $?"
echo '{"stop_hook_active":true}' | .github/hooks/end-of-turn.sh; echo "exit: $?"   # expect no output
```
