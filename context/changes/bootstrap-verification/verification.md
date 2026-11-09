---
bootstrapped_at: 2026-11-09T15:27:29Z
starter_id: fastapi
starter_name: FastAPI
project_name: sales-order-orchestrator
language_family: python
package_manager: uv
cwd_strategy: native-cwd
bootstrapper_confidence: first-class
phase_3_status: ok
audit_command: pip-audit
---

# Bootstrap verification

## Hand-off

```yaml
starter_id: fastapi
package_manager: uv
project_name: sales-order-orchestrator
hints:
  language_family: python
  team_size: solo
  deployment_target: fly
  ci_provider: github-actions
  ci_default_flow: auto-deploy-on-merge
  bootstrapper_confidence: first-class
  path_taken: custom
  quality_override: false
  self_check_answers:
    typed: true
    from_official_starter: true
    conventions: true
    docs_current: true
    can_judge_agent: true
  has_auth: true
  has_payments: false
  has_realtime: true
  has_ai: true
  has_background_jobs: true
```

**Why this stack** (verbatim): Solo developer building a 6-week portfolio MVP for an AI Engineer role, where the core value is an agent orchestrator with structured outputs, dependency-aware parallel checks, a deterministic policy engine and per-step cost visibility. The user named FastAPI and Python, rejecting the Django default for web apps: FastAPI clears all four agent-friendly gates, its Pydantic schemas double as LLM structured-output contracts, agent interfaces and API models, and native async fits parallel agent checks and live run updates. PostgreSQL holds mock company data, audit trail and run state; background work (test mailbox polling, agent runs) stays on Postgres to avoid heavy infrastructure like Temporal or RabbitMQ. FastAPI ships no auth or ORM, so simple test-account login and SQLModel/SQLAlchemy are added on top. A separate React + TypeScript frontend for the inbox and run view is a second toolchain the bootstrapper does not scaffold; it is added manually in the first change. Deploys to Fly via GitHub Actions with auto-deploy on merge; the five-point self-check came back clean.

## Pre-scaffold verification

| Signal      | Value   | Severity | Notes                                                                 |
| ----------- | ------- | -------- | --------------------------------------------------------------------- |
| npm package | not run | n/a      | non-JS starter                                                        |
| GitHub repo | not run | n/a      | card docs_url is https://fastapi.tiangolo.com (not a GitHub URL); no recency signal available. Card `last_updated: 2026-04-22`. |

## Scaffold log

**Resolved invocation**: `uv init . && uv add fastapi uvicorn` (run in `D:\Repos\agent-orchestrator`, uv 0.10.5)
**Strategy**: native-cwd
**Exit code**: 0
**Pre-flight files-to-touch**: pyproject.toml, main.py, README.md, .python-version, .gitignore, uv.lock, .venv/, .git/
**Files written by CLI**: 6 files (pyproject.toml, main.py, README.md, .python-version, .gitignore, uv.lock) + 2 directories (.venv/, .git/)
**Pre-existing files preserved**: context/, .claude/ (untouched)

Notes:
- `uv init` initialised a git repository (`.git/`) by default. No commits were made.
- uv named the project `agent-orchestrator` in `pyproject.toml` (from the directory name), not `sales-order-orchestrator` from the hand-off.
- Interpreter resolved: CPython 3.14.3; `requires-python = ">=3.14"`.
- Installed: fastapi 0.162.2, uvicorn 0.54.0, pydantic 2.14.3, starlette 1.10.0 (+10 transitive). uv warned that hardlinking failed and fell back to copying (cache and project on different drives) — harmless.

## Post-scaffold audit

**Tool**: pip-audit (run as `uvx --from pip-audit python -m pip_audit -r <uv export requirements> --format json`; the `pip-audit.exe` shim was blocked by Windows Application Control, os error 4551, so the module form was used)
**Summary**: 0 CRITICAL, 0 HIGH, 0 MODERATE, 0 LOW — 14 locked dependencies audited, no known vulnerabilities
**Direct vs transitive**: not distinguished by this tool (2 direct: fastapi, uvicorn; 12 transitive)

#### CRITICAL findings

None.

#### HIGH findings

None.

#### MODERATE findings

None.

#### LOW / INFO findings

None.

## Hints recorded but not acted on

| Hint                    | Value                |
| ----------------------- | -------------------- |
| bootstrapper_confidence | first-class          |
| quality_override        | false                |
| path_taken              | custom               |
| self_check_answers      | typed: true, from_official_starter: true, conventions: true, docs_current: true, can_judge_agent: true |
| team_size               | solo                 |
| deployment_target       | fly                  |
| ci_provider             | github-actions       |
| ci_default_flow         | auto-deploy-on-merge |
| has_auth                | true                 |
| has_payments            | false                |
| has_realtime            | true                 |
| has_ai                  | true                 |
| has_background_jobs     | true                 |

## Next steps

Next: a future skill will set up agent context (CLAUDE.md, AGENTS.md). For now, your project is scaffolded and verified — happy hacking.

Useful manual steps in the meantime:
- `git init` was already run by `uv init`; make your first commit when ready.
- Review any `.scaffold` siblings the conflict policy created and decide which version of each file to keep (none in this run).
- Address audit findings per your project's risk tolerance — the full breakdown is in this log (clean tree in this run).
- Consider renaming the project in `pyproject.toml` to `sales-order-orchestrator`.
- Add the React + TypeScript frontend toolchain manually in the first change.
