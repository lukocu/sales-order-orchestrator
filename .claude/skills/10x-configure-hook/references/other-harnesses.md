# Other harnesses — links and capability notes

Verified on: 2026-09-25

This skill does not generate config for these harnesses: the facts below are too thin to prove a hook end to end. Explain the limitation to the user, link the doc, and — if they want to proceed — follow the doc and run the same proof cases (Step 7) by hand.

## Detection signals

`.devin/` or `.windsurf/` (`hooks.json`, `.windsurfrules`), `.gemini/settings.json` or `GEMINI.md`, `.opencode/` or `opencode.json`, `.kiro/hooks/`, `~/.junie/config.json`.

## Notes

- **Devin Desktop (formerly Windsurf Cascade)** — https://docs.devin.ai/desktop/cascade/hooks
  Config `.devin/hooks.json` (the legacy `.windsurf/hooks.json` is used only when `.devin/hooks.json` is absent or empty), user `~/.codeium/windsurf/hooks.json`; 12 events, per-edit event `post_write_code`. Only **pre-hooks can block** (exit 2). **Post-hooks cannot block**; the exit-code table says the agent sees stderr on exit 2, but the doc does not confirm that for post-hooks — treat per-edit feedback as unproven. `show_output` shows hook output to the user in the UI.

- **Gemini CLI** — https://geminicli.com/docs/hooks/
  Config in `.gemini/settings.json` (then `~/.gemini/settings.json`, system, extensions). Per-edit `AfterTool` (can block the result or add context), end of turn `AfterAgent` (retry / halt). Matchers are regexes. Exit 0 → stdout parsed as JSON; exit 2 → stderr used as the rejection reason. Check the timeout unit in the doc — its example uses `5000`.

- **OpenCode** — https://opencode.ai/docs/plugins/
  No shell-hook config: JS/TS plugins in `.opencode/plugins/` or `~/.config/opencode/plugins/` subscribe to events such as `tool.execute.after`, `file.edited`, `session.idle`. Blocking = throwing in a `before` handler. How to feed text back to the model from `after` is not documented.

- **Kiro** — https://kiro.dev/docs/hooks/
  JSON hooks in `.kiro/hooks/` (e.g. `PostFileSave` with a regex matcher), action `command` or `agent` (injects a prompt). File-save and post-tool hooks **cannot block**; pre-tool and prompt-submit hooks can. File-save hooks are IDE-only; default timeout 60 s.

- **Junie (JetBrains)** — https://junie.jetbrains.com/docs/junie-cli-hooks.html
  Junie CLI only, Early Access. Config `~/.junie/config.json` or extension `hooks/hooks.json`; project-local hooks are skipped. **No `PostToolUse`** (per-edit hooks are not possible); `Stop` can block with exit 2 + stderr or `{"decision": "block", "reason": "..."}`.

For any harness without a per-edit feedback channel, move the checks to the end-of-turn event if it can send the agent back, otherwise to the git pre-commit gate — and say so in the report.
