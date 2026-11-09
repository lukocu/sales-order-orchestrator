# Tool wiring — per-tool paths for `/10x-e2e-setup`

This is the only place where `/10x-e2e-setup` branches per agent tool. `SKILL.md`
stays tool-neutral and looks values up here by the tool id.

The rows mirror the 10x-cli tool profiles (`src/lib/tool-profile.ts` in
`@przeprogramowani/10x-cli`): the same `tool` ids, rules files, skill
directories and manifest directories that `10x-cli get` writes.

## Which tool is this?

Resolve the tool id in this order and stop at the first hit:

1. **Manifest next to this skill.** The skill runs from `<manifest dir>/skills/10x-e2e-setup/`.
   If `<manifest dir>/.10x-cli-manifest.json` exists, read its top-level `tool`.
2. **Newest manifest in the project.** Check every _manifest dir_ in the table
   below for `.10x-cli-manifest.json` and take the `tool` from the one with the
   latest `lastApplied`. (After a tool switch an old manifest can stay behind —
   that is why the one next to the skill wins.)
3. **Where this skill is installed.** No manifest (the skills were copied by
   hand): match the directory this skill runs from against the _skill dir_
   column. Every skill dir maps to exactly one tool.
4. **Ask the user**, offering the tool ids below.

The legacy id `windsurf` means `devin-desktop`.

## Per-tool table

| `tool` id       | Tool                              | Rules file                        | Skill dir         | Manifest dir | `playwright-cli install --skills=`         | How the user invokes a skill                                                                                   |
| --------------- | --------------------------------- | --------------------------------- | ----------------- | ------------ | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| `claude-code`   | Claude Code                       | `CLAUDE.md`                       | `.claude/skills/` | `.claude/`   | `claude`                                   | `/10x-e2e <risk-id>`                                                                                           |
| `cursor`        | Cursor                            | `.cursor/rules/10x-course.mdc`    | `.cursor/skills/` | `.cursor/`   | `agents`, then copy (see below)            | `/10x-e2e <risk-id>` in the Agent chat                                                                         |
| `copilot`       | GitHub Copilot                    | `.github/copilot-instructions.md` | `.github/skills/` | `.github/`   | `agents`, then copy                        | `/10x-e2e <risk-id>` in Copilot Chat (agent mode)                                                              |
| `codex`         | Codex CLI                         | `AGENTS.md`                       | `.agents/skills/` | `.agents/`   | `agents` (already the skill dir — no copy) | `$10x-e2e <risk-id>`, or pick it from `/skills`                                                                |
| `devin-desktop` | Devin Desktop (formerly Windsurf) | `AGENTS.md`                       | `.devin/skills/`  | `.devin/`    | `agents`, then copy                        | `@10x-e2e` in Cascade ([docs](https://docs.devin.ai/desktop/cascade/skills)); plain language also works        |
| `gemini`        | Gemini CLI                        | `GEMINI.md`                       | `.gemini/skills/` | `.gemini/`   | `agents`, then copy                        | plain language, or pick it from `/skills`                                                                      |
| `kiro`          | Kiro                              | `AGENTS.md`                       | `.kiro/skills/`   | `.kiro/`     | `agents`, then copy                        | `/10x-e2e` (skills appear as slash commands, [docs](https://kiro.dev/docs/skills/)); plain language also works |
| `generic`       | Other / generic                   | `AGENTS.md`                       | `.ai/skills/`     | `.ai/`       | `agents`, then copy                        | plain language: "read `.ai/skills/10x-e2e/SKILL.md` and follow it for risk <risk-id>"                          |

Notes on the table:

- The invocation column is what to print in the hand-off. Slash syntax for tools
  other than Claude Code and Codex changes between releases — when unsure, the
  plain-language form ("use the 10x-e2e skill for …") works in every tool.

## Wiring `playwright-cli` into the agent

`/10x-e2e` explores the running app with the `playwright-cli` shell command.
The agent needs the binary on `PATH` and, ideally, the CLI's own command skill.

1. **Global CLI.** Check `playwright-cli --version`. If it is missing:

   ```bash
   npm i -g @playwright/cli@latest
   ```

   If a global install is not allowed on the machine, every command also works as
   `npx -y @playwright/cli <command>`; record that prefix in `test-stack.md`.

2. **Command skill.** Skip this step when `<skill dir>/playwright-cli/SKILL.md`
   already exists. Otherwise run, from the project root:

   ```bash
   playwright-cli install --skills=<value from the table>
   ```

   - `--skills` accepts only `claude` (the default) and `agents`. **Any other
     value silently installs to `.claude/skills/`** — never pass a tool id.
   - `claude` writes `.claude/skills/playwright-cli/`; `agents` writes
     `.agents/skills/playwright-cli/` (`SKILL.md` + `references/`).
   - **"then copy"** rows: copy `.agents/skills/playwright-cli/` into the tool's
     skill dir as `<skill dir>/playwright-cli/`. The `.agents/` copy can stay; if
     `.agents/` did not exist before, delete it to keep the tree clean. If you
     cannot copy, skip the skill: the agent can learn the commands from
     `playwright-cli --help` and `playwright-cli --help <command>`.

3. **What `install` also does** (verified on `@playwright/cli` 0.1.21):
   - creates an empty `.playwright/` directory (the CLI workspace marker);
   - appends `.playwright-cli/` (snapshots, console logs — may contain
     credentials) to `.gitignore`, under a comment line, **only when the project
     is a git repository** and no `.playwright-cli/` line is there yet (step 3
     usually added it already);
   - picks a browser: it reuses an installed Chrome if it finds one; otherwise
     install one with `playwright-cli install-browser`.
   - Re-running it is safe: it does not append the `.gitignore` line twice and
     overwrites the skill with the same files.

4. **Check the wiring.** `playwright-cli --version` prints a version, and the
   skill file exists at `<skill dir>/playwright-cli/SKILL.md` (or you recorded
   the `--help` fallback).

Playwright's own packaged test agents (`npx playwright init-agents`) are not part
of this setup: `/10x-e2e` plans and generates tests itself through
`playwright-cli`.

## One browser session per project

`playwright-cli` keeps a machine-wide `default` browser session. Two projects explored at the same time (or one after another without `close`) share it: a command meant for one app can land in the other app's browser, including a `fill` with a password. Name the session after the project on every call, e.g. `playwright-cli -s=<repo-name> open <url>`, and `playwright-cli -s=<repo-name> close` when you are done.
